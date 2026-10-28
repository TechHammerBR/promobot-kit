# 09 — Novo coletor (nova fonte de ofertas)

**Leia antes:** `docs/02-arquitetura.md`, `docs/12-riscos-e-termos.md` (seção 3), e o código de um coletor simples em `src/app/collectors/`.

```text
TAREFA: criar um coletor para a fonte: <nome e URL>.

ANTES DE ESCREVER CÓDIGO
1. Verifique se existe API/feed oficial (RSS, JSON). Prefira isso à raspagem.
2. Leia o robots.txt e os termos da fonte. Se proibirem raspagem automatizada ou houver captcha, PARE e me explique as alternativas.
3. Diga se a fonte gera COMISSÃO (loja com meu afiliado) ou é "bônus" (só movimenta o grupo).

IMPLEMENTAÇÃO
- Um arquivo em src/app/collectors/, herdando de Collector (base.py), devolvendo RawOffer (schemas.py): título, URL, preço, preço antigo, foto, fonte, cupom/pagamento se houver.
- Respeite: 1 requisição/segundo, retry exponencial, User-Agent honesto; 403/429/captcha → BlockedError (a fonte pausa); 0 itens quando costuma haver → LayoutChangedError.
- Registre em collectors/__init__.py. Configurações novas em config.py (com padrão seguro, DESLIGADO por padrão).
- Se a loja tiver afiliado, ligue em affiliate.py (link do MEU programa). Se não, trate como bônus (sem comissão) e deixe isso explícito.
- Testes: tests/ com HTML/JSON de exemplo salvo (sem acessar a internet no teste).

VALIDAÇÃO
1. Rode a coleta isolada e mostre 10 itens (título, preço, URL, foto).
2. Rode o robô em simulação por 1 dia; mostre taxa de aprovação, motivos de rejeição e 10 posts simulados.
3. Confira que uma falha dessa fonte NÃO derruba as outras.

NÃO FAÇA: burlar captcha, usar proxies para fugir de bloqueio, copiar a curadoria de outro grupo, ligar por padrão.
```
