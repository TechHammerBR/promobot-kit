import os

# O Smart App Control do Windows bloqueia as extensões Cython do SQLAlchemy;
# a versão em Python puro é suficiente para este volume.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
