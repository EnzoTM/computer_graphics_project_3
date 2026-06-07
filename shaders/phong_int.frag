#version 330 core

in vec2  vUV;
in vec3  vNormal;
in vec3  vFragPos;
out vec4 FragColor;

uniform sampler2D uDiffuse;
uniform float     uUVTile;
uniform vec3      uCamPos;

uniform float uKa;
uniform float uKd;
uniform float uKs;
uniform float uShininess;

uniform float uAmbientIntensity;
uniform float uDiffuseMult;
uniform float uSpecularMult;

uniform vec3  uLight1Pos;   // lampada (teto)
uniform vec3  uLight1Color;
uniform int   uLight1On;

uniform vec3  uLight2Pos;   // monitor/orbe (mesa)
uniform vec3  uLight2Color;
uniform int   uLight2On;

uniform vec3  uLight3Pos;   // medusa (exterior, só casco)
uniform vec3  uLight3Color;
uniform int   uLight3On;

// 0 = mobília/piso interior; 1 = casco do submarino.
uniform int   uHullMode;

// Atenuação quadrática para a lampada (range ~20m).
// O monitor/orbe não tem atenuação — ilumina o interior inteiro com tom azul,
// como uma tela de monitor que preenche o ambiente.
float lamp_attenuation(vec3 lightPos) {
    float d = length(lightPos - vFragPos);
    return 1.0 / (1.0 + 0.025 * d + 0.003 * d * d);
}

vec3 phong_contrib(vec3 lightDir, vec3 norm, vec3 viewDir,
                   vec3 lightColor, vec3 texColor, float att) {
    float diff    = max(dot(norm, lightDir), 0.0);
    vec3 diffuse  = uKd * uDiffuseMult * diff * lightColor * texColor;

    vec3 reflDir  = reflect(-lightDir, norm);
    float spec    = pow(max(dot(viewDir, reflDir), 0.0), uShininess);
    vec3 specular = uKs * uSpecularMult * spec * lightColor;

    return (diffuse + specular) * att;
}

void main() {
    vec2 uv       = vUV * uUVTile;
    vec3 texColor = texture(uDiffuse, uv).rgb;
    vec3 norm     = normalize(vNormal);
    vec3 viewDir  = normalize(uCamPos - vFragPos);

    vec3 result   = uKa * uAmbientIntensity * texColor;

    if (uHullMode == 1) {
        // Casco do submarino: separa exterior (medusa, front-face) de interior
        // (lampada + monitor, back-face com normal invertida para dentro).
        if (gl_FrontFacing) {
            if (uLight3On == 1)
                result += phong_contrib(normalize(uLight3Pos - vFragPos),
                                        norm, viewDir, uLight3Color, texColor, 1.0);
        } else {
            norm = -norm;
            if (uLight1On == 1)
                result += phong_contrib(normalize(uLight1Pos - vFragPos),
                                        norm, viewDir, uLight1Color, texColor,
                                        lamp_attenuation(uLight1Pos));
            if (uLight2On == 1)
                result += phong_contrib(normalize(uLight2Pos - vFragPos),
                                        norm, viewDir, uLight2Color, texColor, 1.0);
        }
    } else {
        // Mobília e piso interior: usa as normais do mesh diretamente, sem
        // inverter por gl_FrontFacing. Os chãos procedurais têm normais corretas
        // mas winding invertido; inverter quebraria a iluminação deles.
        if (uLight1On == 1)
            result += phong_contrib(normalize(uLight1Pos - vFragPos),
                                    norm, viewDir, uLight1Color, texColor,
                                    lamp_attenuation(uLight1Pos));
        if (uLight2On == 1)
            result += phong_contrib(normalize(uLight2Pos - vFragPos),
                                    norm, viewDir, uLight2Color, texColor, 1.0);
    }

    FragColor = vec4(result, 1.0);
}
