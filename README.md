# 🥚 Sistema de Controle e Monitoramento de Estoque de Ovos

Este é um sistema simples e eficiente para produtores de ovos gerenciarem seu estoque, registrarem a produção diária e visualizarem o histórico através de gráficos interativos.

## 🚀 Funcionalidades

- **Autenticação**: Sistema de login e cadastro de usuários.
- **Registro de Produção**: Interface fácil para inserir a quantidade de ovos colhidos no dia.
- **Visualização de Dados**: Gráfico dos últimos 30 dias de produção para acompanhamento de tendências.
- **Interface Moderna**: Versão web estilizada com CSS customizado via Streamlit.

## 🛠️ Tecnologias Utilizadas

- [Python](https://www.python.org/)
- [SQLite](https://www.sqlite.org/) (Banco de dados local)
- [Streamlit](https://streamlit.io/) (Interface Web)
- [Pandas](https://pandas.pydata.org/) & [Matplotlib](https://matplotlib.org/) (Processamento e visualização de dados)

## 📦 Como rodar o projeto

### 1. Clonar o repositório
```bash
git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio
```

### 2. Instalar as dependências
```bash
pip install streamlit pandas matplotlib
```

### 3. Executar o aplicativo
```bash
streamlit run app.py
```

## 📂 Estrutura de Arquivos

- `app.py`: Código principal da aplicação Streamlit.
- `estoque_ovos.db`: Banco de dados SQLite (gerado automaticamente).
- `requirements.txt`: Lista de bibliotecas necessárias.
- `.gitignore`: Arquivo para evitar o envio de arquivos desnecessários ao Git.
- `LICENSE`: Termos de uso do projeto (Licença MIT).

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---
Desenvolvido com ❤️ para facilitar a gestão rural.
