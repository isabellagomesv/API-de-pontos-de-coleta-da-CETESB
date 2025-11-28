import os

os.environ["GOOGLE_API_KEY"] = "AIzaSyC_A3Z3etglhWEHbekX9hSp9QMm1ytIuQ0"

import json
from typing import List, Dict

import requests
from pyproj import Transformer
from langchain.tools import tool
from langchain.agents import create_agent

MODEL_ID = "google_genai:gemini-2.5-flash-lite"

BASE_FILTER = (
    "(sites <> '#N/D') "
    "AND (score >= 90) "
    "AND (user_estado = 'São Paulo')"
)

WASTE_FILTERS = {
    "pneus": "(user_pneus IS NOT NULL)",
    "embalagens_em_geral": "(user_embalagens_em_geral IS NOT NULL)",
    "baterias_chumbo": "(user_baterias_chumbo_ácido = 'sim')",
    "oleo_comestivel": "(user_óleo_comestível IS NOT NULL)",
    "medicamentos": "(user_medicamentos_domiciliares_ IS NOT NULL)",
    "embalagens_tintas": "(user_embalagens_de_tintas_imobi = 'sim')",
    "eletronicos": "(user_produtos_eletroeletrônicos IS NOT NULL)",
    "pilhas_baterias": "(user_pilhas_e_baterias_portátei IS NOT NULL)",
    "oleo_lubrificante": "(user_óleo_lubrificante_automoti IS NOT NULL)",
    "embalagens_agrotoxicos": "(user_embalagens_de_agrotóxicos_ = 'sim')",
}

ALIASES = {
    "pneus": [
        "pneu",
        "pneus",
        "roda",
        "roda de carro",
        "pneu de carro",
        "pneu de moto",
        "pne",
    ],
    "embalagens_em_geral": [
        "embalagem",
        "embalagens",
        "embalagens em geral",
        "sacola",
        "plástico",
        "plastico",
        "metal",
        "vidro",
    ],
    "baterias_chumbo": [
        "bateria de carro",
        "bateria de moto",
        "baterias de chumbo",
        "bateria automotiva",
        "chumbo ácido",
    ],
    "oleo_comestivel": [
        "óleo de cozinha",
        "oleo de cozinha",
        "oleo comestivel",
        "óleo comestível",
        "óleo usado",
    ],
    "medicamentos": [
        "remédio",
        "remedios",
        "medicamentos",
        "remédio vencido",
        "remédio velho",
    ],
    "embalagens_tintas": [
        "tinta",
        "latinha de tinta",
        "embalagens de tinta",
    ],
    "eletronicos": [
        "eletrônico",
        "eletrônicos",
        "eletronico",
        "eletroeletrônico",
        "tv",
        "televisão",
        "computador",
        "notebook",
        "celular",
    ],
    "pilhas_baterias": [
        "pilha",
        "pilhas",
        "bateria pequena",
        "baterias portáteis",
        "pilhas e baterias",
    ],
    "oleo_lubrificante": [
        "óleo lubrificante",
        "oleo lubrificante",
        "óleo de motor",
        "óleo de carro",
    ],
    "embalagens_agrotoxicos": [
        "agrotóxico",
        "agrotoxico",
        "embalagens de agrotóxicos",
    ],
}

def normalize_waste_type(user_input: str) -> str:
    text = user_input.lower()
    for key, synonyms in ALIASES.items():
        for s in synonyms:
            if s in text:
                return key
    return "embalagens_em_geral"

def get_lat_lon_from_cep(cep: str) -> Dict[str, float]:
    cep = cep.replace("-", "").strip()

    via_cep_url = f"https://viacep.com.br/ws/{cep}/json/"
    r = requests.get(via_cep_url, timeout=10)
    r.raise_for_status()
    data = r.json()

    if data.get("erro"):
        raise ValueError(f"CEP {cep} não encontrado no ViaCEP.")

    logradouro = data.get("logradouro", "")
    bairro = data.get("bairro", "")
    localidade = data.get("localidade", "")
    uf = data.get("uf", "")

    queries: List[str] = []

    if logradouro and bairro:
        queries.append(f"{logradouro}, {bairro}, {localidade}, {uf}, Brasil")

    if logradouro:
        queries.append(f"{logradouro}, {localidade}, {uf}, Brasil")

    queries.append(f"{cep}, {localidade}, {uf}, Brasil")
    queries.append(f"{cep}, Brasil")

    nominatim_url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "cetesb-lixo-bot/1.0 (contato@exemplo.com)"
    }

    last_query = None
    for q in queries:
        last_query = q
        params = {
            "q": q,
            "format": "json",
            "limit": 1,
        }
        resp = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            return {"lat": lat, "lon": lon, "query": q}

    raise ValueError(
        f"Não foi possível geocodificar o CEP {cep}. "
        f"Tentativas de consulta no Nominatim falharam (ex: '{last_query}')."
    )

def latlon_to_webmercator(lat: float, lon: float) -> Dict[str, float]:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x, y = transformer.transform(lon, lat)
    return {"x": x, "y": y}

CETESB_URL = (
    "https://arcgis.cetesb.sp.gov.br/server/rest/services/Hosted/"
    "empresas_coleta_log_reversa/FeatureServer/0/query"
)


@tool
def find_recycling_points(cep: str, waste_type: str) -> List[Dict[str, str]]:
    """
    Dado um CEP brasileiro e um tipo de resíduo (por exemplo: pneus, pilhas,
    eletrônicos, óleo de cozinha, medicamentos, embalagens, baterias, etc.),
    encontra até 3 pontos de coleta da CETESB mais próximos no estado de São Paulo.
    """
    try:
        canonical_type = normalize_waste_type(waste_type)

        if canonical_type not in WASTE_FILTERS:
            raise ValueError(
                f"Tipo de resíduo não suportado: '{waste_type}'. "
                f"Tente algo como 'pneus', 'pilhas e baterias', 'óleo de cozinha', etc."
            )

        where = f"{BASE_FILTER} AND {WASTE_FILTERS[canonical_type]}"

        cep_info = get_lat_lon_from_cep(cep)
        lat = cep_info["lat"]
        lon = cep_info["lon"]
        wm = latlon_to_webmercator(lat, lon)

        geometry = {
            "x": wm["x"],
            "y": wm["y"],
            "spatialReference": {"wkid": 102100},
        }

        data = {
            "f": "json",
            "where": where,
            "geometry": json.dumps(geometry),
            "geometryType": "esriGeometryPoint",
            "inSR": 102100,
            "spatialRel": "esriSpatialRelIntersects",
            "distance": 30000,
            "units": "esriSRUnit_Meter",
            "returnGeometry": "true",
            "outFields": "*",
            "outSR": 102100,
            "orderByFields": "distance",
            "resultRecordCount": 10,
        }

        resp = requests.post(CETESB_URL, data=data, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        features = payload.get("features", [])
        if not features:
            raise ValueError(
                f"Não encontrei pontos de coleta próximos para '{waste_type}' "
                f"no CEP {cep}. Tente outro CEP ou outro tipo de resíduo."
            )

        def distance_of(feature):
            return feature.get("attributes", {}).get("distance", float("inf"))

        features_sorted = sorted(features, key=distance_of)
        top3 = features_sorted[:3]

        results: List[Dict[str, str]] = []

        for f in top3:
            attrs = f.get("attributes", {})
            nome = (
                attrs.get("user_razão_social")
                or attrs.get("user_razão_social_1")
                or attrs.get("user_razão_social_12")
                or "Ponto de coleta"
            )
            endereco = (
                attrs.get("place_addr")
                or attrs.get("longlabel")
                or f"{attrs.get('user_endereco', '')}, {attrs.get('user_bairro', '')}"
            )
            cidade = attrs.get("user_cidade", "")
            estado = attrs.get("user_estado", "")
            site = attrs.get("sites", "")
            distancia = attrs.get("distance")

            results.append(
                {
                    "nome": nome,
                    "endereco": endereco,
                    "cidade": cidade,
                    "estado": estado,
                    "site": site,
                    "distance": f"{distancia:.0f} m"
                    if isinstance(distancia, (int, float))
                    else None,
                }
            )

        return results

    except Exception as e:
        return [
            {
                "erro": (
                    "Não consegui localizar pontos de coleta com os dados informados. "
                    f"Detalhe técnico: {str(e)}"
                )
            }
        ]
    
agent = create_agent(
    model=MODEL_ID,
    tools=[find_recycling_points],
    system_prompt=(
        "Você é um assistente especializado em descarte correto de resíduos no "
        "estado de São Paulo.\n"
        "- SEMPRE que o usuário mencionar um CEP brasileiro e QUALQUER tipo de lixo "
        "ou resíduo (incluindo pneus, pilhas, eletrônicos, óleo de cozinha, "
        "medicamentos, embalagens, óleo lubrificante, baterias, etc.), "
        "você deve chamar a ferramenta find_recycling_points passando o CEP e o tipo de resíduo.\n"
        "- Não responda por conta própria sem usar a ferramenta nesses casos.\n"
        "- Responda em português do Brasil.\n"
        "- Liste sempre os 3 pontos de coleta mais próximos, mostrando nome e "
        "endereço, e se possível a distância aproximada."
    ),
)

if __name__ == "__main__":
    print("\n🌱 Bem-vindo ao assistente de descarte consciente de resíduos da CETESB\n")
    while True:
        print("Digite os dados abaixo ou escreva 'sair' para encerrar.\n")

        tipo = input(
            "1) Que tipo de resíduo você quer descartar?\n"
            "   Ex.: pneus, pilhas, eletrônicos, óleo de cozinha, medicamentos\n\n   → "
        )
        if tipo.strip().lower() == "sair":
            print("\nAté a próxima! ♻️\n")
            break

        cep = input(
            "\n2) Informe o seu CEP (apenas números, ex.: 01311000):\n\n   → "
        )
        if cep.strip().lower() == "sair":
            print("\nAté a próxima! ♻️\n")
            break

        mensagem_usuario = f"Quero descartar {tipo} no CEP {cep}"
        msg = {
            "messages": [
                {
                    "role": "user",
                    "content": mensagem_usuario,
                }
            ]
        }

        print("\n🔎 Buscando pontos de coleta mais próximos...\n")

        try:
            result = agent.invoke(msg)
            last_message = result["messages"][-1]
            print("✅ Resultado:\n")
            print(last_message.content)
        except Exception as e:
            print("\n❌ Ocorreu um erro ao consultar o agente.")
            print(f"Detalhe técnico: {e}")

        continuar = input(
            "\nDeseja buscar outro ponto de coleta? (s/n): "
        ).strip().lower()
        if continuar not in ("s", "sim"):
            print(
                "\nObrigado por descartar seus resíduos de forma correta! 🌍♻️\n"
            )
            break