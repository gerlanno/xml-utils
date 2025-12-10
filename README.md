# XML Utils - Análise de Pré Disparos

Este projeto fornece uma ferramenta para análise de arquivos XML de títulos de cancelamento, extraindo devedores, protocolos e gerando indicadores.

## Estrutura do Projeto

- `app/main.py`: Código principal da aplicação Streamlit.
- `src/`: Módulos auxiliares (parser, metrics, viz).
- `styles/`: Arquivos CSS.
- `assets/`: Imagens e logos.

## Como EXECUTAR com Docker (Recomendado)

Certifique-se de ter o [Docker](https://www.docker.com/products/docker-desktop/) e o [Docker Compose](https://docs.docker.com/compose/install/) instalados.

1. Construa e inicie o container:
   ```bash
   docker-compose up --build
   ```

2. Acesse a aplicação no navegador:
   [http://localhost:8501](http://localhost:8501)

3. Para parar a execução:
   Pressione `Ctrl+C` no terminal ou rode:
   ```bash
   docker-compose down
   ```

## Desenvolvimento Local (sem Docker)

1. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\Scripts\activate     # Windows
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
   *Nota: No Windows, pode ser necessário instalar bibliotecas adicionais para o `python-magic` (dlls).*

3. Execute a aplicação:
   ```bash
   streamlit run app/main.py
   ```
