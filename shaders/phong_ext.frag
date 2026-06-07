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

// Luz direcional da água — simula a luz solar filtrada pela superfície.
// Raios paralelos vindos de cima: matematicamente equivale a infinitos pontos
// de luz na mesma direção, por isso ilumina todo o exterior uniformemente.
uniform vec3  uWaterDir;    // direção normalizada PARA a fonte (ex: (0,1,0) = de baixo pra cima)
uniform vec3  uWaterColor;  // tom azul-esverdeado subaquático
uniform int   uWaterOn;

// Luz pontual da medusa — boost local/bioluminescente
uniform vec3  uLightPos;
uniform vec3  uLightColor;
uniform int   uLightOn;

void main() {
    vec2 uv       = vUV * uUVTile;
    vec3 texColor = texture(uDiffuse, uv).rgb;
    vec3 norm     = normalize(vNormal);
    vec3 viewDir  = normalize(uCamPos - vFragPos);

    // Componente ambiente
    vec3 result = uKa * uAmbientIntensity * texColor;

    // Luz direcional da água (vem de cima, raios paralelos)
    if (uWaterOn == 1) {
        vec3  ld   = normalize(uWaterDir);
        float diff = max(dot(norm, ld), 0.0);
        result += uKd * uDiffuseMult * diff * uWaterColor * texColor;
    }

    // Luz pontual da medusa
    if (uLightOn == 1) {
        vec3  lightDir = normalize(uLightPos - vFragPos);
        float diff     = max(dot(norm, lightDir), 0.0);
        vec3  diffuse  = uKd * uDiffuseMult * diff * uLightColor * texColor;

        vec3  reflDir  = reflect(-lightDir, norm);
        float spec     = pow(max(dot(viewDir, reflDir), 0.0), uShininess);
        vec3  specular = uKs * uSpecularMult * spec * uLightColor;

        result += diffuse + specular;
    }

    FragColor = vec4(result, 1.0);
}
