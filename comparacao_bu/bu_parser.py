"""Leitor mínimo do boletim de urna binário do TSE (o03221{uf}{mun}{zona}{secao}-bu.dat, ASN.1 DER), sem dependências.

O imgbu (texto) não está publicado no 2º turno de 2026 (NoSuchKey), então usamos o BU binário, que tem os mesmos números.
Estrutura observada (tags implícitas de contexto, conforme bu.asn1 do TSE):

  EntidadeEnvelopeGenerico SEQ { cabecalho SEQ{dataGeracao, [2] idEleicao/pleito}, fase ENUM, [0] identificacao, tipoEnvelope ENUM,
                                 conteudo OCTET STRING }
  conteudo = EntidadeBoletimUrna SEQ {
      cabecalho, fase, urna SEQ, identificacaoSecao SEQ{SEQ{municipio, zona}, local, secao}, dataHoraEmissao, [0] dadosSecao,
      INTEGER, [1] SEQ{...}, resultadosVotacaoPorEleicao SEQ OF ResultadoVotacaoPorEleicao, ... }
  ResultadoVotacaoPorEleicao SEQ { idEleicao INT, INT, INT, INT, resultadosVotacao SEQ OF ResultadoVotacao, OCTET, OCTET }
      (os três inteiros após idEleicao: 1º = eleitores aptos da seção; guardados como `aptos` e `extras`)
  ResultadoVotacao SEQ { tipoCargo ENUM, qtdComparecimento INT, totaisVotosCargo SEQ OF TotalVotosCargo }
  TotalVotosCargo SEQ { [1] codigoCargo (1 = presidente, 3 = governador), ordemImpressao INT, votosVotaveis SEQ OF TotalVotosVotavel }
  TotalVotosVotavel SEQ { [1] tipoVoto, [2] quantidadeVotos, [3] identificacaoVotavel SEQ{partido, codigo} OPCIONAL, INT, OCTET }
  TipoVoto: 1 nominal, 2 branco, 3 nulo, 4 legenda, 5+ outros (contados como nulos aqui).
"""
from dataclasses import dataclass, field

TIPO_NOMINAL, TIPO_BRANCO, TIPO_NULO, TIPO_LEGENDA = 1, 2, 3, 4
CARGO_PRESIDENTE = 1


@dataclass
class Node:
    cls: int          # 0 universal, 1 application, 2 context, 3 private
    constructed: bool
    tag: int
    value: bytes
    children: list = field(default_factory=list)

    def int(self):
        return int.from_bytes(self.value, "big", signed=True) if self.value else 0

    def text(self):
        return self.value.decode("latin-1")

    @property
    def is_seq(self):
        return self.cls == 0 and self.tag == 16 and self.constructed

    @property
    def is_int(self):
        return self.cls == 0 and self.tag == 2 and not self.constructed

    @property
    def is_enum(self):
        return self.cls == 0 and self.tag == 10 and not self.constructed


def _tlv(data, pos):
    first = data[pos]
    pos += 1
    cls, constructed, tag = first >> 6, bool(first & 0x20), first & 0x1F
    if tag == 0x1F:  # tag em forma longa
        tag = 0
        while True:
            b = data[pos]
            pos += 1
            tag = (tag << 7) | (b & 0x7F)
            if not b & 0x80:
                break
    length = data[pos]
    pos += 1
    if length & 0x80:
        nbytes = length & 0x7F
        if nbytes == 0:
            raise ValueError("comprimento indefinido não suportado")
        length = int.from_bytes(data[pos:pos + nbytes], "big")
        pos += nbytes
    end = pos + length
    if end > len(data):
        raise ValueError("TLV truncado")
    return cls, constructed, tag, data[pos:end], end


def decode_all(data):
    nodes, pos = [], 0
    while pos < len(data):
        cls, constructed, tag, value, pos = _tlv(data, pos)
        node = Node(cls, constructed, tag, value)
        if constructed:
            node.children = decode_all(value)
        nodes.append(node)
    return nodes


def decode(data):
    nodes = decode_all(data)
    if len(nodes) != 1:
        raise ValueError(f"esperado 1 elemento no topo, encontrados {len(nodes)}")
    return nodes[0]


def dump(node, depth=0, out=None):
    out = [] if out is None else out
    pad = "  " * depth
    kind = {0: "U", 1: "A", 2: "C", 3: "P"}[node.cls]
    if node.constructed:
        out.append(f"{pad}{kind}{node.tag} ({len(node.children)})")
        for c in node.children:
            dump(c, depth + 1, out)
    else:
        if node.cls == 0 and node.tag in (2, 10):
            v = node.int()
        elif node.cls == 0 and node.tag in (27, 26, 22, 12, 19):
            v = repr(node.text())
        else:
            v = node.value[:24].hex() + ("…" if len(node.value) > 24 else "")
            if node.cls == 2 and len(node.value) <= 4:
                v += f" (= {node.int()})"
        out.append(f"{pad}{kind}{node.tag} {v}")
    return out


def unwrap(env):
    """EntidadeEnvelopeGenerico → EntidadeBoletimUrna (último OCTET STRING universal do envelope)."""
    if not env.is_seq:
        raise ValueError("envelope não é SEQUENCE")
    octets = [c for c in env.children if c.cls == 0 and c.tag == 4 and not c.constructed]
    if not octets:
        raise ValueError("envelope sem conteúdo")
    return decode(octets[-1].value)


@dataclass
class ResultadoCargo:
    id_eleicao: int
    aptos: int
    extras: tuple
    comparecimento: int
    codigo_cargo: int
    votos: dict      # número do votável -> votos nominais
    brancos: int
    nulos: int
    legenda: int

    @property
    def total(self):
        return sum(self.votos.values()) + self.brancos + self.nulos + self.legenda


@dataclass
class BU:
    municipio: int
    zona: int
    secao: int
    emissao: str
    resultados: list

    def presidente(self):
        rs = [r for r in self.resultados if r.codigo_cargo == CARGO_PRESIDENTE]
        if len(rs) != 1:
            raise ValueError(f"esperado 1 resultado de presidente, encontrados {len(rs)}")
        return rs[0]


def _primitives(node):
    return [c for c in node.children if not c.constructed]


def _votavel(v):
    prims = _primitives(v)
    if len(prims) < 2:
        raise ValueError("TotalVotosVotavel sem tipo/quantidade")
    tipo, qtd = prims[0].int(), prims[1].int()
    ident = next((c for c in v.children if c.constructed and len(c.children) >= 2 and all(x.is_int for x in c.children)), None)
    return tipo, qtd, (ident.children[-1].int() if ident else None)


def _resultado_por_eleicao(rve):
    """SEQ{idEleicao INT, INT..., SEQ OF ResultadoVotacao, ...} → lista de ResultadoCargo, ou None se não casar."""
    ch = rve.children
    if not (rve.is_seq and len(ch) >= 3 and ch[0].is_int and ch[1].is_int):
        return None
    ints = []
    for c in ch:
        if not c.is_int:
            break
        ints.append(c.int())
    lists = [c for c in ch if c.is_seq]
    if not lists:
        return None
    out = []
    for rv in lists[0].children:
        if not (rv.is_seq and len(rv.children) >= 3 and rv.children[0].is_enum and rv.children[1].is_int and rv.children[2].is_seq):
            return None
        comparecimento = rv.children[1].int()
        for tvc in rv.children[2].children:
            if not (tvc.is_seq and len(tvc.children) >= 3 and tvc.children[-1].is_seq):
                return None
            cod = tvc.children[0]
            codigo = cod.int() if not cod.constructed else cod.children[0].int()
            votos, brancos, nulos, legenda = {}, 0, 0, 0
            for v in tvc.children[-1].children:
                tipo, qtd, numero = _votavel(v)
                if tipo == TIPO_NOMINAL:
                    if numero is None:
                        raise ValueError("voto nominal sem identificação do votável")
                    votos[numero] = votos.get(numero, 0) + qtd
                elif tipo == TIPO_BRANCO:
                    brancos += qtd
                elif tipo == TIPO_LEGENDA:
                    legenda += qtd
                else:
                    nulos += qtd
            out.append(ResultadoCargo(ints[0], ints[1], tuple(ints[2:]), comparecimento, codigo, votos, brancos, nulos, legenda))
    return out


def parse_bu(data):
    bu = unwrap(decode(data))
    ident = next((c for c in bu.children if c.is_seq and len(c.children) == 3 and c.children[0].is_seq
                  and len(c.children[0].children) == 2 and all(x.is_int for x in c.children[0].children)
                  and c.children[2].is_int), None)
    if ident is None:
        raise ValueError("BU sem identificacaoSecao")
    mun, zona = (x.int() for x in ident.children[0].children)
    secao = ident.children[2].int()
    emissao = next((c.text() for c in bu.children if c.cls == 0 and c.tag == 27), "")
    resultados = []
    for cand in bu.children:
        if not cand.is_seq or cand is ident:
            continue
        parsed = [_resultado_por_eleicao(rve) for rve in cand.children]
        if parsed and all(p is not None for p in parsed):
            for p in parsed:
                resultados.extend(p)
    if not resultados:
        raise ValueError("BU sem resultadosVotacaoPorEleicao reconhecível")
    # dataHoraEmissao é a 2ª GeneralString direta do BU (a 1ª está no cabeçalho)
    strings = [c.text() for c in bu.children if c.cls == 0 and c.tag == 27]
    return BU(mun, zona, secao, strings[0] if strings else emissao, resultados)


if __name__ == "__main__":
    import sys
    raw = open(sys.argv[1], "rb").read()
    env = decode(raw)
    print("\n".join(dump(env)))
    print("---- conteudo ----")
    print("\n".join(dump(unwrap(env))))
    b = parse_bu(raw)
    print(b.municipio, b.zona, b.secao, b.emissao)
    for r in b.resultados:
        print(r)
