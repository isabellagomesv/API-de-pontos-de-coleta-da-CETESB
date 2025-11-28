🗑️ ♻️ API-de-pontos-de-coleta – CETESB + IA

Este projeto implementa um agente inteligente capaz de:

-receber um CEP,
-converter para coordenadas Web Mercator,
-consultar a API oficial da CETESB,
-e retornar os 3 pontos de coleta de resíduos mais próximos do usuário.

O sistema utiliza:

-LangChain
-Google GenAI (Gemini)
-PyProj
-Requests

Ideal para aplicações de sustentabilidade, logística reversa e educação ambiental.

🚀 Funcionalidades

-Busca dinâmica de empresas licenciadas pela CETESB.
-Filtro por tipo de resíduo.
-Conversão automática de CEP → latitude/longitude → Web Mercator.
-Seleção dos 3 pontos mais próximos do usuário.
-Agente LangChain estruturado.

🔧 Instalação
1. Clone o repositório
git clone https://github.com/SEU_USUARIO/NOME_DO_REPO.git
cd NOME_DO_REPO

2. Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

3. Instale as dependências
pip install -r requirements.txt

🔐 Configuração do .env

Crie um arquivo chamado .env:

GOOGLE_API_KEY=sua_chave_aqui

👉 Nunca suba sua chave para o GitHub.

▶️ Como executar
python main.py


O programa irá solicitar um CEP e o tipo de resíduo desejado.

📦 Estrutura do Projeto
/seu-projeto
│
├── main.py
├── requirements.txt
├── README.md
└── .gitignore

🧪 Exemplo de uso

Entrada:

Tipo de resíduo: pneus
CEP: 01311000

Saída:

Empresa A – 1.2 km
Empresa B – 1.7 km
Empresa C – 2.3 km
