"""Contagem por seção a partir do log da urna, na mesma definição do boletim de urna do TSE.

QT_ELEI_BIOM_SEM_HABILITACAO (TSE) = eleitores com biometria que não foram habilitados por ela. No log:
- a urna só pede a digital ("Solicita digital. Tentativa N de M") a quem tem biometria cadastrada;
- "Tipo de habilitação do eleitor [biométrica]" marca quem foi habilitado pela digital.
Cada voto ("O voto do eleitor foi computado") fecha a sessão aberta em "Aguardando digitação do identificador".
"""


def count_lines(lines, day):
    votos = pediu = bio = 0
    sess_pediu = sess_bio = False
    for line in lines:
        r = line.rstrip("\n").split("\t")
        if len(r) < 5 or not r[0].startswith(day):
            continue
        msg = r[4]
        if msg.startswith("Aguardando digitação do identificador"):
            sess_pediu = sess_bio = False
        elif msg.startswith("Solicita digital. Tentativa"):
            sess_pediu = True
        elif msg.startswith("Tipo de habilitação do eleitor [biométrica]"):
            sess_bio = True
        elif msg == "O voto do eleitor foi computado":
            votos += 1
            pediu += sess_pediu
            bio += sess_bio
            sess_pediu = sess_bio = False
    # votos de quem tem biometria e não foi habilitado por ela (definição do TSE) e votos sem biometria em geral
    return {"votos": votos, "com_biometria": pediu, "biom_sem_hab": pediu - min(pediu, bio), "habilitados_bio": bio,
            "sem_bio_total": votos - bio}
