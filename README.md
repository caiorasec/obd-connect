# OBD Connect para Home Assistant

Integração personalizada que recebe a telemetria enviada pelo aplicativo Android HR-V Connect. Versão inicial 0.1.0, testada com Home Assistant 2026.11.0.

Cria nove sensores (RPM, velocidade, temperaturas, carga, acelerador, MAP e tensões), recebe lotes autenticados, mantém histórico/recibos SQLite e confirma registros apenas após persistir. Reenvios são deduplicados; leituras antigas não substituem as recentes. GPS e simulações não são aceitos.

O aplicativo Android é um projeto separado (`../hrv-connect` no ambiente local); não faz parte deste pacote. Durante a coleta, ele envia lotes a cada 60 segundos. Fora dela, o agendamento depende do Android.

## Instalar

Consulte [instalação e pareamento](docs/OBD_CONNECT_SETUP.md). O código fica em `custom_components/obd_connect/`. A instalação manual consiste em copiar essa pasta para o diretório de configuração do Home Assistant, reiniciar e adicionar OBD Connect em Dispositivos e serviços.

## Testar com Docker

```bash
docker compose --profile ha run --rm ha-tests
```

Usa imagem oficial fixada por digest e dados fictícios temporários. Não acessa o carro, o telefone ou o Home Assistant residencial. Os 12 testes cobrem persistência, deduplicação, autenticação HTTP, sensores, expiração automática e recarga.

## Empacotar

```bash
python3 tools/package_integration.py
```

Gera `artifacts/obd-connect-0.1.0.zip` e checksum. O pacote contém o componente, metadados locais e instruções.

## Estado de publicação

Repositório Git local, sem remote e sem publicação. A estrutura para Marketplace/HACS está presente; antes de publicar, definir URL GitHub, documentação/issues públicos, codeowners, marca e licença, e executar as validações Hassfest/Marketplace. Não foram usados endereços, responsáveis ou licença fictícios.

A conexão pelo Home Assistant residencial, inclusive Nabu Casa, ainda depende de configuração e validação. [Contrato e limites](docs/PHASE_3.md). O histórico privado é armazenado em `.storage/obd_connect/` dentro da configuração do Home Assistant e deve entrar no backup.
