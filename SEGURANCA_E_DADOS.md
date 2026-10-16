# Segurança e persistência de dados — Multi Analytics

## Contas e isolamento

- O aplicativo exige login e permite criar uma conta com e-mail e senha.
- As senhas não são armazenadas em texto puro: é guardado um hash PBKDF2-HMAC-SHA256 com salt aleatório.
- Cada conta recebe seu próprio identificador numérico (`users.id`).
- Consultores têm `user_id`; lançamentos têm `user_id` e `consultant_id`.
- As consultas, alterações e exclusões são filtradas pelo identificador da sessão autenticada. O banco também valida que o consultor relacionado pertence à mesma conta.
- O cadastro inicial cria consultores padrão (`Loja`, `Angela`, `Camila` e `Juliana`); cada usuário pode adicionar e gerenciar seus próprios consultores.

## Banco persistente

Por padrão, o aplicativo usa o arquivo SQLite `multi_analytics.db` no diretório de execução. Para escolher outro caminho, configure a variável de ambiente `MULTI_ANALYTICS_DB`.

Exemplo no PowerShell:

```powershell
$env:MULTI_ANALYTICS_DB = "D:\DadosMulti\multi_analytics.db"
python -m streamlit run Sistema_Multi.py
```

Em hospedagens, configure `MULTI_ANALYTICS_DB` para um volume/disco persistente. Se o provedor apagar arquivos locais ao reiniciar ou redeployar a aplicação, o banco precisa ficar em armazenamento persistente ou em um banco gerenciado. Não coloque o arquivo SQLite no GitHub nem em uma pasta pública.

## Dados legados

O arquivo histórico `dadosmulti.csv` não é importado automaticamente: ele não contém identificadores de proprietário e atribuí-lo a uma conta sem confirmação poderia expor dados de outra pessoa. O arquivo legado ainda está no histórico do repositório e deve ser revisado pelo proprietário antes de tornar o repositório público ou compartilhar seu conteúdo. A nova aplicação não lê esse CSV.

## Recomendações antes de produção

- Publique o aplicativo apenas por HTTPS.
- Restrinja permissões administrativas e o acesso ao volume que contém o banco.
- Configure backups regulares do arquivo SQLite e teste a restauração.
- Para muitos usuários simultâneos ou implantação em várias instâncias, prefira PostgreSQL ou outro banco gerenciado.
- Esta implementação fornece isolamento no nível da aplicação e do banco; não criptografa o arquivo SQLite em repouso.
