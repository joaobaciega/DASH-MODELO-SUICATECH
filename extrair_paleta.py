"""
Extrai a paleta da logo da Suiçatech e prepara as versões usadas no app.

    python extrair_paleta.py

O que faz:
  1. Lê assets/logo_suicatech.jpg (arquivo original da logo, sem alteração).
  2. Mede as três cores dominantes: o fundo, o vermelho do "SUIÇA TECH" e o
     grafite do "INTRACE Br". Usa a cor mais frequente de cada grupo de pixels
     (a moda), que é a cor "chapada" da arte — a média puxaria a cor para as
     bordas suavizadas do JPEG.
  3. Deriva as variações do tema escuro do app: o fundo é o grafite da logo e
     as demais cores são misturas dele com o branco e o vermelho (fundo
     secundário, grade, texto, vermelho para texto pequeno, paleta de séries).
     Confere o contraste de cada uma contra o fundo (WCAG 2.1).
  4. Gera assets/logo_suicatech.png (fundo transparente, cores originais, para
     fundo claro), assets/logo_suicatech_escuro.png (o "INTRACE Br" grafite
     passa para o texto claro do tema, para aparecer no fundo escuro) e
     assets/icone.png (o símbolo da logo, usado como ícone da aba).

As cores impressas aqui são as mesmas fixadas em tema.py e .streamlit/config.toml.
Rodar de novo só é necessário se a logo mudar.
"""

from pathlib import Path

import numpy as np
from PIL import Image

PASTA = Path(__file__).resolve().parent
LOGO = PASTA / "assets" / "logo_suicatech.jpg"


def hexa(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[int(round(c)) for c in rgb])


def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def luminancia(cor):
    c = rgb(cor) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(a, b):
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mistura(a, b, t):
    """t = 0 devolve a; t = 1 devolve b."""
    return hexa(rgb(a) * (1 - t) + rgb(b) * t)


def moda(pixels):
    valores, contagem = np.unique(pixels, axis=0, return_counts=True)
    return hexa(valores[np.argmax(contagem)])


def cores_dominantes(px):
    """Fundo, vermelho e grafite, com a fatia de pixels de cada grupo."""
    mx, mn = px.max(1), px.min(1)
    sat = (mx - mn) / np.maximum(mx, 1)
    grupos = {
        "fundo": px[mn > 235],
        "vermelho": px[(sat > 0.75) & (px[:, 0] > 150)],
        "grafite": px[mx < 90],
    }
    return {nome: (moda(p), len(p) / len(px)) for nome, p in grupos.items()}


def logo_transparente(img):
    """Remove o fundo branco sem serrilhar as bordas.

    A arte é vermelho/grafite sobre branco; nas bordas o JPEG mistura as duas.
    Como o menor canal do vermelho e do grafite fica perto de 30, a fração de
    tinta de cada pixel é (255 - menor canal) / 225. Com ela recupera-se a cor
    original da tinta e a transparência proporcional.
    """
    a = np.asarray(img.convert("RGB")).astype(float)
    alfa = np.clip((255 - a.min(axis=2)) / 225, 0, 1)
    seguro = np.maximum(alfa, 1e-6)[..., None]
    cor = np.clip((a - (1 - alfa[..., None]) * 255) / seguro, 0, 255)
    rgba = np.dstack([cor, alfa * 255]).astype(np.uint8)
    out = Image.fromarray(rgba, "RGBA")
    return out.crop(out.getbbox())


def logo_fundo_escuro(logo_rgba, claro):
    """Mesma logo, com a tinta grafite trocada por `claro` (o texto do tema).

    O vermelho fica como está. A máscara do grafite é a tinta escura, neutra e opaca,
    alargada em 4 px para cobrir as bordas suavizadas das letras; o texto
    "INTRACE Br" fica longe do vermelho, então a máscara não encosta nele.
    Dentro da máscara só a cor muda; a transparência é a mesma.
    """
    from PIL import ImageFilter

    a = np.asarray(logo_rgba).astype(float)
    cor, alfa = a[..., :3], a[..., 3]
    neutro = (cor.max(axis=2) - cor.min(axis=2)) < 40       # grafite não tem matiz
    escuro = (cor.max(axis=2) < 120) & neutro & (alfa > 128)
    mascara = Image.fromarray((escuro * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))
    mascara = np.asarray(mascara)[..., None] > 0
    nova = np.where(mascara, rgb(claro), cor)
    return Image.fromarray(np.dstack([nova, alfa]).round().astype(np.uint8), "RGBA")


def icone(logo_rgba):
    """Recorta o símbolo vermelho à esquerda do texto e centraliza num quadrado."""
    a = np.asarray(logo_rgba)
    cols = np.where(a[..., 3].max(axis=0) > 0)[0]
    # O símbolo termina na primeira coluna vazia depois do início da arte.
    vazias = np.where(a[:, cols[0]:, 3].max(axis=0) == 0)[0]
    fim = cols[0] + (vazias[0] if len(vazias) else a.shape[1])
    simbolo = logo_rgba.crop((0, 0, fim, logo_rgba.height))
    simbolo = simbolo.crop(simbolo.getbbox())
    lado = max(simbolo.size) + 8
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.paste(simbolo, ((lado - simbolo.width) // 2, (lado - simbolo.height) // 2), simbolo)
    return tela.resize((128, 128), Image.LANCZOS)


def main():
    img = Image.open(LOGO)
    px = np.asarray(img.convert("RGB")).reshape(-1, 3).astype(int)
    dom = cores_dominantes(px)
    fundo, vermelho, grafite = dom["fundo"][0], dom["vermelho"][0], dom["grafite"][0]

    print("Cores dominantes da logo (moda de cada grupo):")
    for nome, (cor, fatia) in dom.items():
        print(f"  {nome:9} {cor}  {fatia:6.1%} dos pixels")

    # Tema escuro: o fundo do app é o grafite da logo; o resto sai de misturas
    # do grafite com o branco (neutros) e do vermelho com o branco (acentos).
    escuro = grafite
    derivadas = {
        "fundo_secundario": mistura(grafite, fundo, 0.07),   # barra lateral, cartões
        "linha_grade": mistura(grafite, fundo, 0.15),        # grade e divisores
        "texto": mistura(fundo, grafite, 0.08),              # branco suavizado
        "texto_suave": mistura(grafite, fundo, 0.62),        # notas e legendas
        "cinza_serie": mistura(grafite, fundo, 0.45),        # barras sem destaque
    }
    # Vermelho para texto pequeno: clareia o vermelho da logo em direção ao
    # branco até passar 4,5:1 sobre o fundo secundário (o mais exigente).
    t = 0.0
    while contraste(mistura(vermelho, fundo, t), derivadas["fundo_secundario"]) < 4.5:
        t += 0.01
    derivadas["vermelho_claro"] = mistura(vermelho, fundo, t)
    # Botões e tags (texto branco sobre o vermelho): escurece até 4,5:1.
    t = 0.0
    while contraste(fundo, mistura(vermelho, grafite, t)) < 4.5:
        t += 0.01
    derivadas["vermelho_botao"] = mistura(vermelho, grafite, t)

    # Séries: todas com 3:1 ou mais sobre o fundo escuro, alternando claro e
    # médio para que vizinhas se distingam também para daltônicos.
    paleta = [
        vermelho,                          # 1 série principal
        mistura(grafite, fundo, 0.85),     # 2 cinza muito claro
        mistura(vermelho, fundo, 0.30),    # 3 vermelho claro
        mistura(grafite, fundo, 0.70),     # 4 cinza claro
        derivadas["cinza_serie"],          # 5 cinza médio
        mistura(vermelho, fundo, 0.60),    # 6 rosado
        mistura(vermelho, fundo, 0.15),    # 7 vermelho aberto
        mistura(grafite, fundo, 0.65),     # 8 cinza
    ]

    print(f"\nTema escuro — fundo {escuro} (grafite da logo):")
    for nome, cor in derivadas.items():
        print(f"  {nome:17} {cor}  contraste s/ fundo {contraste(cor, escuro):5.2f}:1")
    sec = derivadas["fundo_secundario"]
    print("\nContrastes principais:")
    print(f"  texto {derivadas['texto']} s/ fundo: {contraste(derivadas['texto'], escuro):.2f}:1 "
          f"· s/ secundário: {contraste(derivadas['texto'], sec):.2f}:1")
    print(f"  vermelho {vermelho} s/ fundo: {contraste(vermelho, escuro):.2f}:1 "
          "(gráficos e títulos grandes: mínimo 3:1)")
    print(f"  vermelho_claro {derivadas['vermelho_claro']} s/ secundário: "
          f"{contraste(derivadas['vermelho_claro'], sec):.2f}:1")
    print(f"  branco s/ vermelho_botao {derivadas['vermelho_botao']}: "
          f"{contraste(fundo, derivadas['vermelho_botao']):.2f}:1")
    print("\nPaleta de séries (contraste s/ fundo):")
    for i, cor in enumerate(paleta, 1):
        print(f"  {i:2} {cor}  {contraste(cor, escuro):5.2f}:1")

    logo_png = logo_transparente(img)
    logo_png.save(PASTA / "assets" / "logo_suicatech.png")
    logo_fundo_escuro(logo_png, derivadas["texto"]).save(
        PASTA / "assets" / "logo_suicatech_escuro.png")
    icone(logo_png).save(PASTA / "assets" / "icone.png")
    print("\nGerados: assets/logo_suicatech.png, assets/logo_suicatech_escuro.png "
          "e assets/icone.png")


if __name__ == "__main__":
    main()
