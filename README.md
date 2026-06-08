# Projeto 3: Iluminação Phong

**SCC0250, Computação Gráfica · 2026.1 · ICMC-USP**

Feito por:
**Enzo Tonon Morente - 14568476**
**Cauê Paiva Lira - 14675416**

---

## 1. Visão geral

Extensão do Projeto 2: o cenário submarino 3D recebe iluminação **Phong completa** (ambiente + difusa + especular) implementada em GLSL 3.30 core, sem nenhuma função de pipeline fixo (`glLight`, `glMaterial`, etc.).

A cena continua dividida em duas zonas:

- **Exterior**: submarino, leito de areia, *skydome* oceânico, decoração procedural (corais, pedras e algas), cardume de peixes-palhaço, orca, beluga — iluminados por **luz direcional subaquática** (simula sol filtrado pela água) e pela **medusa bioluminescente** (fonte de luz móvel).
- **Interior**: corredor metálico com cadeira *sci-fi*, estação de monitoramento, mesa de controle, joystick UAV e lâmpada industrial — iluminados pela **lâmpada no teto** e pelo **monitor da estação de trabalho**.

A separação interior/exterior é implementada no shader via `uHullMode` + `gl_FrontFacing`: faces externas do casco reagem apenas à medusa; faces internas reagem apenas à lâmpada e ao monitor.

| | |
|---|---|
| Linguagem | Python 3.12 |
| Engine | OpenGL 3.3 core profile, **sem pipeline fixo** |
| Matrizes | `numpy` + `mat4` uniforms nos shaders |
| Iluminação | **Phong** (ambiente + difusa + especular) em GLSL — `phong_ext` (exterior) e `phong_int` (interior) |
| Modelos `.obj` | **13** modelos importados, todos texturizados, vários com múltiplos materiais |
| Parâmetros de material | `ka`, `kd`, `ks`, `shininess` definidos por objeto no código, **não lidos dos `.mtl`** |

---

## 2. Como executar

```bash
git clone <url-do-repositório>
cd projeto_3
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

Testado em **macOS 25.3** (Apple Silicon) e **Ubuntu 22.04** com Python **3.12**.

> **Importante:** usar Python 3.12 especificamente. O `assimp_py` (usado no pipeline de build offline em `tools/`) ainda não tem *wheel* para 3.13+. O runtime (`src/`) só depende de PyOpenGL, GLFW, numpy e Pillow — mas manter 3.12 evita surpresas.
>
> Para instalar outra versão do Python sem afetar o sistema, use o [pyenv](https://realpython.com/intro-to-pyenv/).

---

## 3. Controles

| Tecla | Ação |
|---|---|
| `W` `A` `S` `D` | Movimento horizontal da câmera (FPS) |
| `Espaço` / `Shift` | Subir / descer |
| `Mouse` | Olhar em volta (yaw + pitch) |
| `↑` `↓` `←` `→` | Mover a **medusa** (fonte de luz exterior) em XZ |
| `1` | Toggle da luz da medusa (exterior) |
| `2` | Toggle da lâmpada (interior) |
| `3` | Toggle do monitor (interior) |
| `4` | Toggle da luz direcional da água (exterior) |
| `+` / `-` | Aumentar / diminuir intensidade **ambiente** (passo 0.05, range 0–1) |
| `]` / `[` | Aumentar / diminuir componente **difusa** (passo 0.1, range 0–2) |
| `R` / `T` | Aumentar / diminuir componente **especular** (passo 0.1, range 0–2) |
| `Esc` | Sair |

> Os controles de P2 (escala da orca, rotação da beluga, translação da cadeira, wireframe) foram **removidos**, conforme o Requisito 8 do edital.

---

## 4. Sistema de iluminação

### 4.1 Dois shaders Phong

O projeto usa dois programas GLSL separados para isolar completamente as iluminações:

| Shader | Usado para | Fontes de luz |
|---|---|---|
| `phong_ext` | Exterior (chão, decoração, animais, medusa) | Luz direcional da água + medusa (ponto) |
| `phong_int` | Interior (casco do submarino, piso metálico, mobília) | Lâmpada (ponto, com atenuação) + monitor (ponto, sem atenuação) |

O **skydome** continua com seu shader próprio (`skydome.vert/frag`), inalterado.

### 4.2 Modelo Phong por fragmento

Cada fragmento calcula:

```
resultado = Ka * I_ambiente * texColor
          + Kd * diff_mult * max(dot(N, L), 0) * lightColor * texColor    (difuso)
          + Ks * spec_mult * pow(max(dot(V, R), 0), shininess) * lightColor  (especular)
```

Onde `N` é a normal do vértice transformada pela **normal matrix** (`mat3(transpose(inverse(uModel)))`), `L` é a direção à fonte, `V` a direção à câmera e `R` o vetor refletido.

### 4.3 Separação exterior/interior no casco

O submarino é uma malha única — as mesmas faces formam tanto a parede externa quanto a parede interna da cabine. Para separar a iluminação:

- O casco é renderizado com `uHullMode = 1`
- `gl_FrontFacing == true` → face externa → recebe **apenas** a medusa
- `gl_FrontFacing == false` → face interna → normal invertida → recebe **lâmpada + monitor**
- Toda a mobília e pisos usam `uHullMode = 0` e recebem lâmpada + monitor diretamente

Isso garante que a medusa nunca "vaza" para o interior, e que a lâmpada nunca ilumina o exterior.

### 4.4 Luz direcional da água (exterior)

Em vez de múltiplos pontos de luz simulando a superfície do oceano, o shader usa uma **luz direcional** (vetor constante `(0.15, 1.0, 0.05)`, normalizado no shader). Matematicamente equivale a infinitas fontes paralelas da mesma direção — ilumina todo o exterior uniformemente com um tom azul-esverdeado subaquático, como a luz solar filtrada pela água.

### 4.5 Atenuação

- **Lâmpada**: atenuação quadrática `1 / (1 + 0.025·d + 0.003·d²)` — alcance ~20 m, cai gradualmente com a distância
- **Monitor**: sem atenuação (`att = 1.0`) — funciona como tela que preenche o ambiente inteiro com luz azul difusa
- **Medusa**: sem atenuação no exterior — bioluminescência como boost local sobre a luz direcional

### 4.6 Parâmetros de material por objeto

Cada `Object3D` define seus próprios `ka`, `kd`, `ks` e `shininess`, enviados como uniforms ao shader a cada drawcall. Nenhum parâmetro vem dos arquivos `.mtl`.

| Objeto | ka | kd | ks | shininess |
|---|---|---|---|---|
| submarino | 0.2 | 0.7 | 0.5 | 64 |
| orca / beluga | 0.3 | 0.8 | 0.2 | 16 |
| peixe-palhaço | 0.3 | 0.8 | 0.1 | 8 |
| coral / alga | 0.3 | 0.7 | 0.1 | 8 |
| pedra | 0.2 | 0.6 | 0.1 | 8 |
| medusa | 0.4 | 0.6 | 0.5 | 32 |
| cadeira / estação | 0.2 | 0.6 | 0.5–0.6 | 32–48 |
| mesa | 0.2 | 0.5 | 0.7 | 64 |
| joystick | 0.2 | 0.6 | 0.8 | 128 |
| lâmpada | 0.3 | 0.5 | 0.9 | 128 |

---

## 5. Modelos 3D

O projeto usa **13 modelos** `.obj` texturizados:

| Modelo | Zona | Materiais | Papel |
|---|---|---|---|
| `submarino` | Interior (casco) | 1 | Delimita os dois ambientes; casco renderizado com `uHullMode=1` |
| `coral` | Exterior | 1 | Decoração procedural do leito |
| `pedra` | Exterior | 1 | Decoração procedural do leito |
| `alga` | Exterior | 1 | Decoração procedural do leito |
| `peixe_palhaco` | Exterior | 5 | Cardume procedural em alturas variadas |
| `orca` | Exterior | 1 | Animal de grande porte |
| `beluga` | Exterior | 1 | Animal de grande porte |
| `jelly_fish` | Exterior | 1 | **Fonte de luz exterior**, movível pelas setas |
| `cadeira` | Interior | 13 | Cadeira do piloto |
| `estacao` | Interior | 2 | Estação de monitoramento |
| `mesa` | Interior | 10 | Console *sci-fi* na popa |
| `joystick_2` | Interior | 11 | Joystick UAV |
| `lamp` | Interior | 4 | **Fonte de luz interior** (lâmpada no teto) |

A decoração exterior é **procedural**: grid 40×40 com *jitter* aleatório e semente fixa (`seed=42`), garantindo a mesma cena a cada execução.

---

## 6. Cenário externo

O exterior abrange um leito de areia de 400 m × 400 m (textura 4K *tiled* 40×), skydome esférico de raio 250 m ancorado à câmera, e decoração procedural cobrindo toda a área visível com exclusão em volta do casco.

A iluminação vem de duas fontes: a **luz direcional da água** (sempre ativa, cobre tudo uniformemente) e a **medusa** (bioluminescente, movível, funciona como boost local). As setas movem a medusa no plano XZ em passos de 0.5 m; a tecla `1` a desliga/liga.

---

## 7. Cenário interno

O interior segue a curvatura real do casco: `make_hull_following_floor` lê o `.obj` do submarino, determina a largura do casco a cada fatia Z e gera um piso de metal escovado que acompanha a forma interna da popa à proa.

A iluminação é dupla:
- **Lâmpada** (tecla `2`): luz branco-quente `(1.0, 0.95, 0.8)` no teto `(0, 8, 1)`, com atenuação quadrática suave
- **Monitor** (tecla `3`): luz azul `(0.2, 0.5, 1.0)` na estação de trabalho `(0, 4.2, 19.5)`, sem atenuação — preenche o ambiente com brilho de tela

---

## 8. Atendimento ao edital

| # | Requisito | Como está implementado |
|---|---|---|
| 1 | Objeto externo com translação = fonte de luz exterior que **só afeta o exterior** | Medusa (`jelly_fish.obj`) é movida pelas setas; sua posição vira `uLightPos` no `phong_ext`. O `phong_int` recebe a posição da medusa como `uLight3` mas só a aplica na face externa do casco (`gl_FrontFacing && uHullMode==1`) |
| 2 | Dois objetos internos como fontes de luz de **cores diferentes** que **só afetam o interior** | Lâmpada (branco-quente) e monitor (azul) em `phong_int`; objetos exteriores usam `phong_ext` que não declara essas luzes |
| 3 | Toggle independente de cada luz por teclado | `1` = medusa, `2` = lâmpada, `3` = monitor, `4` = luz direcional da água; cada um altera um campo de `LightState` enviado como `int` uniform (`uLightOn`/`uWaterOn`) ao shader |
| 4 | Incrementar/decrementar luz ambiente | `+`/`-`: `lights.ambient` ±0.05, clampado em [0, 1], enviado como `uAmbientIntensity` |
| 5 | Incrementar/decrementar reflexão difusa | `]`/`[`: `lights.diffuse_mult` ±0.1, clampado em [0, 2], enviado como `uDiffuseMult` |
| 6 | Incrementar/decrementar reflexão especular | `R`/`T`: `lights.specular_mult` ±0.1, clampado em [0, 2], enviado como `uSpecularMult` |
| 7 | Cada objeto com **parâmetros próprios** de iluminação (não dos `.mtl`) | `Object3D` tem campos `ka`, `kd`, `ks`, `shininess`; enviados como uniforms antes de cada `draw_model()`; valores na tabela da §4.6 |
| 8 | Eventos de teclado do P2 **não precisam** mais existir | Controles de escala/rotação/translação/wireframe removidos de `main.py` |

---

## 9. Estrutura do projeto

```
projeto_3/
├── src/
│   ├── main.py        janela GLFW + input + loop principal
│   ├── camera.py      câmera FPS (yaw/pitch + clamp de bounds) — intocado do P2
│   ├── utils.py       matrizes 4×4 (translate/rotate/scale/perspective/look_at) — intocado
│   ├── model.py       loader .obj: parser vn, VBO 8 floats/vértice [xyz·uv·nxyz], multi-material
│   ├── shader.py      compile/link + cache de uniforms — intocado
│   ├── texture.py     PIL → glTexImage2D — intocado
│   └── scene.py       montagem da cena, LightState, split ext/int, decoração procedural
│
├── shaders/
│   ├── phong_ext.vert / phong_ext.frag   exterior: luz direcional da água + medusa
│   ├── phong_int.vert / phong_int.frag   interior: lâmpada + monitor + hull mode
│   └── skydome.vert  / skydome.frag      skydome panorâmico — intocado do P2
│
├── assets/
│   ├── modelos/       13 pastas com .obj + .mtl + texturas
│   ├── texturas/      chão_externo (areia 4K), interior (metal escovado), skybox
│   └── skybox/        panorama oceânico equirretangular
│
└── tools/
    └── build_assets.py  pipeline offline (.fbx/.blend → .obj) — não necessário para executar
```

### Fluxo de um frame

1. **Input**: GLFW notifica teclas/mouse → `Camera` e `LightState` atualizados
2. **Skydome**: desenhado com `depthMask = false`, ancorado à posição da câmera
3. **Exterior** (`phong_ext`): chão de areia + todos os `ext_objects`; uniforms de luz direcional da água e medusa enviados uma vez antes do loop
4. **Interior** (`phong_int`): piso metálico + todos os `int_objects`; para o casco do submarino `uHullMode=1`, para os demais `uHullMode=0`
5. **Swap**: `glfw.swap_buffers()`

### VBO e normais

O `model.py` lê `vn` do `.obj` e armazena **8 floats por vértice**: `[x, y, z, u, v, nx, ny, nz]`. A normal é transformada no vertex shader pela *normal matrix* `mat3(transpose(inverse(uModel)))`, que preserva a direção correta mesmo com escalas não-uniformes. Primitivas geradas em runtime (`make_floor`, `make_hull_following_floor`) usam normal `(0, 1, 0)` explícita.

---

## 10. Observações técnicas

- **Winding order do casco**: os triângulos do submarino têm winding tal que a face geométrica "externa" é a `gl_FrontFacing == true`. Não invertemos as normais por `!gl_FrontFacing` nos objetos de mobília/piso — isso quebraria os pisos procedurais cujos vértices têm normal `(0,1,0)` mas winding invertido.
- **Monitor sem atenuação**: com atenuação quadrática padrão a ~29 m de distância, a contribuição do monitor caia a menos de 2% — imperceptível. A solução foi usar `att = 1.0` para o monitor, mantendo atenuação apenas na lâmpada.
- **Luz direcional vs. múltiplos pontos**: a luz da água usa um único vetor de direção no shader, o que é matematicamente equivalente a infinitos pontos de luz paralelos e computacionalmente mais eficiente do que N fontes pontuais.
- **Python 3.12**: versão obrigatória. O runtime depende apenas de PyOpenGL, GLFW, numpy e Pillow.
