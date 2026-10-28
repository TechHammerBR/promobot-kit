// Conector WhatsApp do PromoBot (Baileys, open source/MIT). SÓ ENVIA posts.
// Privacidade: não LÊ mensagens recebidas (sem chat/comandos); sem histórico; não marca online.
//
// API interna (rede docker, porta 3000):
//   GET  /status                -> {connected, me}
//   GET  /qr                    -> PNG do QR Code atual (204 se já conectado)
//   GET  /groups                -> [{id, name}] grupos onde o número participa (sem participantes)
//   GET  /newsletters           -> [{id, name}] canais (newsletters) do número
//   POST /send {to, text, image|image_b64} -> envia foto+legenda (ou só texto)
//   GET  /pair?number=55DDD...  -> código de pareamento (alternativa ao QR)
//   POST /logout                -> desconecta o número
import http from 'node:http'
import { rmSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import makeWASocket, { DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion, Browsers } from 'baileys'
import QRCode from 'qrcode'
import pino from 'pino'

const DATA_DIR = process.env.WA_DATA_DIR || '/data'
const AUTH_DIR = DATA_DIR + '/auth'
const log = pino({ level: process.env.LOG_LEVEL || 'warn' })
let sock = null
// Contatos: SÓ os números (JIDs), apenas para entregar o Status (exigência do WhatsApp).
// Persistidos em /data/contacts.json (o WhatsApp só envia a lista no pareamento). Nunca expostos pela API.
const CONTACTS_FILE = DATA_DIR + '/contacts.json'
const contacts = new Set(existsSync(CONTACTS_FILE) ? JSON.parse(readFileSync(CONTACTS_FILE, 'utf8')) : [])
let saveTimer = null
function persistContacts() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => writeFileSync(CONTACTS_FILE, JSON.stringify([...contacts]), { mode: 0o600 }), 3000)
}
let lastQr = null
let connected = false

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)
  const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }))
  sock = makeWASocket({
    auth: state,
    version,
    logger: log,
    browser: Browsers.ubuntu('Chrome'), // pareamento exige nome de navegador real
    markOnlineOnConnect: false,
    syncFullHistory: false,
    // sync mínimo exigido pela Baileys (mapeamentos de sessão); nada é armazenado por este serviço
    generateHighQualityLinkPreview: false,
  })
  sock.ev.on('creds.update', saveCreds)
  const addContacts = list => {
    const before = contacts.size
    list.forEach(c => { if (c?.id?.endsWith('@s.whatsapp.net')) contacts.add(c.id) })
    if (contacts.size !== before) persistContacts()
  }
  sock.ev.on('contacts.upsert', addContacts)
  // sincronização inicial (pareamento): pega SÓ os contatos; mensagens/conversas são ignoradas
  sock.ev.on('messaging-history.set', ({ contacts: cs }) => addContacts(cs || []))
  sock.ev.on('contacts.update', addContacts)
  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) lastQr = qr
    if (connection === 'open') {
      connected = true
      lastQr = null
      console.log('wa: conectado como', sock.user?.id)
    }
    if (connection === 'close') {
      connected = false
      const code = lastDisconnect?.error?.output?.statusCode
      console.log('wa: conexão fechada, código', code)
      if (code === DisconnectReason.loggedOut) {
        rmSync(AUTH_DIR, { recursive: true, force: true }) // sessão inválida: volta a pedir QR
      }
      setTimeout(start, code === DisconnectReason.loggedOut ? 2000 : 5000)
    }
  })
}

// ---- convites (14/10/2026): lote diário pequeno, intervalo aleatório de 1,5 a 4 min, para se fora do ar
const CONVITE_FILE = DATA_DIR + '/convites.json'
const convite = { enviados: existsSync(CONVITE_FILE) ? JSON.parse(readFileSync(CONVITE_FILE, 'utf8')) : {}, rodando: false, falhas: 0 }
function conviteResumo() {
  const hoje = new Date().toISOString().slice(0, 10)
  const vals = Object.values(convite.enviados)
  return { contatos: contacts.size, ja_convidados: vals.filter(v => v !== 'falhou').length, hoje: vals.filter(v => v === hoje).length,
           falhas: vals.filter(v => v === 'falhou').length, rodando: convite.rodando }
}
const esperar = ms => new Promise(r => setTimeout(r, ms))
async function conviteLote(fila, text) {
  convite.rodando = true
  convite.falhas = 0
  try {
    for (const jid of fila) {
      if (!connected) break
      try {
        await sock.sendMessage(jid, { text })
        convite.enviados[jid] = new Date().toISOString().slice(0, 10)
        convite.falhas = 0
      } catch (e) {
        convite.enviados[jid] = 'falhou'
        log.warn({ err: String(e) }, 'convite: falhou')
        if (++convite.falhas >= 3) break // 3 erros seguidos: para o lote (pode ser limite do WhatsApp)
      }
      writeFileSync(CONVITE_FILE, JSON.stringify(convite.enviados), { mode: 0o600 })
      await esperar(90000 + Math.random() * 150000)
    }
  } finally {
    convite.rodando = false
  }
}

function json(res, code, body) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(body))
}

async function readBody(req) {
  let data = ''
  for await (const chunk of req) data += chunk
  return data ? JSON.parse(data) : {}
}

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://x')
    if (url.pathname === '/status') return json(res, 200, { connected, me: connected ? sock.user?.id : null })
    if (url.pathname === '/qr') {
      if (connected || !lastQr) return json(res, 204, {})
      res.writeHead(200, { 'Content-Type': 'image/png' })
      return res.end(await QRCode.toBuffer(lastQr, { width: 420, margin: 2 }))
    }
    if (url.pathname === '/pair') { // alternativa ao QR: código de 8 caracteres digitado no celular
      if (connected) return json(res, 200, { connected: true })
      const number = (url.searchParams.get('number') || '').replace(/\D/g, '')
      return json(res, 200, { code: await sock.requestPairingCode(number) })
    }
    if (!connected) return json(res, 503, { error: 'WhatsApp não conectado' })
    if (url.pathname === '/groups') {
      const groups = await sock.groupFetchAllParticipating()
      // comunidade (14/10/2026): mostra se é comunidade, grupo de avisos, a comunidade-mãe, se só admins postam e se este número é admin
      const eu = (sock.user?.id || '').split(':')[0].split('@')[0]
      const euLid = (sock.user?.lid || '').split(':')[0].split('@')[0]
      const meu = v => v && [eu, euLid].includes(String(v).split(':')[0].split('@')[0])
      return json(res, 200, Object.values(groups).map(g => ({
        id: g.id, name: g.subject, community: !!g.isCommunity, announce_group: !!g.isCommunityAnnounce,
        parent: g.linkedParent || null, only_admins: !!g.announce, size: (g.participants || []).length,
        admin: (g.participants || []).some(x => x.admin && [x.id, x.phoneNumber, x.lid].some(meu)),
      })))
    }
    if (url.pathname === '/convite-status') { // só números agregados; a lista nunca sai do processo
      return json(res, 200, conviteResumo())
    }
    if (url.pathname === '/convite-lote' && req.method === 'POST') { // convite em lote, devagar, em segundo plano
      const { text, n, skip_groups } = await readBody(req)
      if (convite.rodando) return json(res, 409, { error: 'lote anterior ainda em andamento', ...conviteResumo() })
      if (!text || !n) return json(res, 400, { error: 'faltou text ou n' })
      const pular = new Set()
      for (const gid of skip_groups || []) { // quem já está nos grupos não recebe convite
        try {
          const g = await sock.groupMetadata(gid)
          for (const x of g.participants || []) [x.id, x.phoneNumber].forEach(v => v && pular.add(String(v).split(':')[0].replace(/@.*/, '')))
        } catch (e) { log.warn({ gid, err: String(e) }, 'convite: grupo ilegível') }
      }
      const eu = (sock.user?.id || '').split(':')[0].split('@')[0]
      const fila = [...contacts].filter(j => {
        const num = j.split('@')[0]
        return num !== eu && !convite.enviados[j] && !pular.has(num)
      }).slice(0, Math.min(Number(n), 100))
      conviteLote(fila, text) // não espera: responde já e envia aos poucos
      return json(res, 200, { ok: true, neste_lote: fila.length, ...conviteResumo() })
    }
    if (url.pathname === '/group-info') { // nome, descrição e regras de um grupo (identidade visual; 14/10/2026)
      const g = await sock.groupMetadata(url.searchParams.get('to'))
      return json(res, 200, { id: g.id, name: g.subject, desc: g.desc || '', only_admins: !!g.announce, locked: !!g.restrict,
                              size: (g.participants || []).length })
    }
    if (url.pathname === '/group-update' && req.method === 'POST') { // identidade do grupo: nome, descrição, foto, só admins
      const { to, subject, description, image_b64, only_admins, locked } = await readBody(req)
      if (subject) await sock.groupUpdateSubject(to, subject)
      if (description !== undefined) await sock.groupUpdateDescription(to, description)
      if (image_b64) await sock.updateProfilePicture(to, Buffer.from(image_b64, 'base64'))
      if (only_admins !== undefined) await sock.groupSettingUpdate(to, only_admins ? 'announcement' : 'not_announcement')
      if (locked !== undefined) await sock.groupSettingUpdate(to, locked ? 'locked' : 'unlocked')
      return json(res, 200, { ok: true })
    }
    if (url.pathname === '/invite') { // link de convite de um grupo (número precisa ser admin)
      const code = await sock.groupInviteCode(url.searchParams.get('to'))
      return json(res, 200, { link: `https://chat.whatsapp.com/${code}` })
    }
    if (url.pathname === '/ephemeral' && req.method === 'POST') { // mensagens temporárias do grupo (0, 86400, 604800, 7776000 s)
      const { to, seconds } = await readBody(req)
      await sock.groupToggleEphemeral(to, Number(seconds))
      return json(res, 200, { ok: true })
    }
    if (url.pathname === '/newsletters') {
      const list = await sock.newsletterSubscribed?.().catch(() => []) ?? []
      return json(res, 200, list.map(n => ({ id: n.id, name: n.thread_metadata?.name?.text || n.name })))
    }
    if (url.pathname === '/send' && req.method === 'POST') {
      const { to, text, image, image_b64 } = await readBody(req)
      const img = image_b64 ? Buffer.from(image_b64, 'base64') : (image ? { url: image } : null)
      const msg = img ? { image: img, caption: text } : { text }
      const sent = await sock.sendMessage(to, msg)
      return json(res, 200, { ok: true, id: sent?.key?.id })
    }
    if (url.pathname === '/status-info') { // só a contagem; a lista nunca sai do processo
      return json(res, 200, { contacts: contacts.size })
    }
    if (url.pathname === '/post-status' && req.method === 'POST') { // Status (stories) do próprio número
      const { text, image_b64 } = await readBody(req)
      if (!contacts.size) return json(res, 409, { error: 'nenhum contato carregado ainda' })
      const me = sock.user.id.replace(/:\d+@/, '@')
      const msg = image_b64 ? { image: Buffer.from(image_b64, 'base64'), caption: text } : { text }
      const sent = await sock.sendMessage('status@broadcast', msg, { statusJidList: [...contacts, me] })
      return json(res, 200, { ok: true, id: sent?.key?.id, audience: contacts.size })
    }
    if (url.pathname === '/logout' && req.method === 'POST') {
      await sock.logout()
      return json(res, 200, { ok: true })
    }
    return json(res, 404, { error: 'not found' })
  } catch (e) {
    return json(res, 500, { error: String(e?.message || e) })
  }
}).listen(3000, () => console.log('wa: API na porta 3000'))

start()
