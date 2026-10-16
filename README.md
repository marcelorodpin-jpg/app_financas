# Gestão Financeira

Aplicação de gestão financeira pessoal em Python, Streamlit e Firebase Firestore.

## Recursos

- Cadastro de usuários e login.
- Senhas armazenadas com hash PBKDF2-HMAC-SHA256 e salt individual; nenhuma senha é salva em texto puro.
- Cadastro, consulta, edição e exclusão de receitas e despesas.
- Resumo de receitas, despesas e saldo.
- Interface responsiva para celular, com resumo no topo, lista em cartões e botão flutuante para adicionar movimentações.
- Cada usuário visualiza e gerencia somente as próprias movimentações.

## Configuração

1. Use Python 3.10 ou superior.
2. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Mantenha o arquivo JSON da conta de serviço Firebase na raiz do projeto. Por segurança, arquivos de credenciais `*firebase-adminsdk*.json` estão excluídos do Git.
4. No Firebase Console, confirme que o Firestore está criado no banco de dados padrão e que a conta de serviço tem permissão para acessá-lo.
5. Inicie a aplicação:

   ```powershell
   streamlit run app.py
   ```

Por padrão, o app procura `app-financas-c2243-firebase-adminsdk-fbsvc-f5cc8404d9.json` na pasta do projeto. Para indicar outro caminho, defina a variável de ambiente `FIREBASE_CREDENTIALS`.

## Coleções Firestore

- `usuarios`: username normalizado, salt e hash da senha, quantidade de iterações e data de cadastro.
- `transacoes`: proprietário, tipo, descrição, categoria, valor, data e timestamps.

O app usa o Firebase Admin SDK no servidor; não coloque a chave de serviço no código, em repositórios públicos ou no cliente. A autenticação é própria da aplicação e não cria usuários no Firebase Authentication.

## Deploy no Streamlit Community Cloud

### 1. Prepare o Firebase com acesso mínimo

1. No Firebase Console, abra o projeto correto e confirme que o Firestore está ativo no banco padrão.
2. Use uma conta de serviço dedicada para esta aplicação. Não use uma conta pessoal nem conceda `Owner` ou `Editor` ao projeto; conceda somente as permissões necessárias para ler e gravar os documentos do Firestore.
3. Se a chave JSON já foi enviada para um repositório remoto, mesmo que o repositório seja privado ou o arquivo tenha sido apagado depois, revogue essa chave no Google Cloud Console e gere outra.

O Firebase Admin SDK acessa o Firestore com permissões de servidor e não depende das regras de segurança do Firestore. A aplicação filtra movimentações pelo usuário no servidor; mantenha o código e o repositório restritos a quem administra o app.

### 2. Publique o código no GitHub sem credenciais

1. Crie um repositório no GitHub, de preferência privado se o código ou a estrutura do projeto não forem públicos.
2. Envie `app.py`, `requirements.txt` e os arquivos de documentação/configuração necessários.
3. **Não** envie `app-financas-c2243-firebase-adminsdk-fbsvc-f5cc8404d9.json` nem `.streamlit/secrets.toml`. O `.gitignore` do projeto já exclui essas credenciais.
4. Se o JSON já estiver rastreado pelo Git, removê-lo da pasta não basta: remova-o do histórico remoto e revogue/rotacione a chave antes de continuar.

### 3. Crie o app no Streamlit Community Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io/) e entre com a conta GitHub que tem acesso ao repositório.
2. Escolha **Create app** e informe o repositório, a branch (por exemplo `main`) e o caminho do arquivo principal: `app.py`.
3. Em **Advanced settings**, selecione Python 3.10 ou superior e configure os secrets conforme o passo seguinte.
4. Clique em **Deploy**. O Community Cloud instalará as dependências de `requirements.txt`.

### 4. Cadastre a chave em Secrets

O arquivo `.streamlit/secrets.toml` é gerado localmente a partir do JSON da conta de serviço. Abra esse arquivo, copie todo o conteúdo e cole no campo **Secrets** das configurações do app no Streamlit Community Cloud. Salve as configurações. Faça isso somente no painel de Secrets; não cole o conteúdo em `app.py`, README, chat, GitHub ou screenshots.

O app lê `st.secrets["firebase"]` no deploy e também aceita o JSON localmente. O `.gitignore` exclui o arquivo `secrets.toml`, então ele não deve ser enviado ao GitHub.

### 5. Verifique a publicação

1. Aguarde o build terminar e consulte os logs do app no painel caso haja erro de dependência ou configuração.
2. Abra a URL publicada e crie um usuário de teste. Cadastre uma receita e uma despesa; confirme o saldo, a listagem e o retorno à lista após salvar.
3. Crie um segundo usuário e confirme que ele não vê as movimentações do primeiro.
4. Verifique no Firebase Console que os documentos aparecem nas coleções `usuarios` e `transacoes`.
5. Não compartilhe os logs ou capturas de tela se contiverem segredos ou dados financeiros.

Para desenvolvimento local, o mesmo `.streamlit/secrets.toml` é carregado automaticamente. Esse arquivo contém a chave privada: mantenha-o apenas na sua máquina e nunca imprima `st.secrets` nos logs.
