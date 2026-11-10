# Fase 3 — OBD Connect, Android 0.4.0 / integração 0.1.1

Implementação local de envio opcional por HTTPS, sem GPS. A instalação residencial aguarda o endereço/versão do servidor. O repositório público é https://github.com/caiorasec/obd-connect e a distribuição usa repositório personalizado Marketplace/HACS; não há inclusão no catálogo público de busca. [Guia de instalação](OBD_CONNECT_SETUP.md).

## Fluxo e execução Android

ELM327 → Room → lotes HTTPS → integração OBD Connect → SQLite histórico/recibos → sensores Home Assistant.

O envio começa desativado. O serviço de coleta REAL tenta enviar a cada 60 segundos, sem sobreposição. Uma tentativa leva no máximo o timeout de conexão/leitura, salvo comportamento do sistema de rede; o cliente usa 10 s de conexão e 15 s de leitura, sem seguir redirecionamentos. Não usa GPS, Bluetooth ou comandos adicionais para sincronizar. A cadência de consultas ao ELM327 permanece independente.

WorkManager agenda trabalho com rede CONNECTED para enviar pendências após a coleta. Há trabalho periódico de 15 minutos e trabalho de retomada com atraso inicial de 60 s, sem promessa de pontualidade fora do serviço ativo. Doze, fabricante e encerramento forçado podem adiar execução. Erros conservam a fila, com atraso progressivo de 60 a 900 s no gerenciador e backoff do WorkManager. Uma resposta parcial válida conserva os rejeitados. O botão Enviar lote agora permite tentativa explícita imediata.

Cada tentativa envia até 256 registros (64 recentes e 192 antigos, deduplicados), equilibrando leituras atuais e recuperação do histórico. Um lote é enviado por tentativa; backlog grande pode levar vários minutos. GPS e simulações nunca entram no payload. Pendências GPS anteriores continuam locais, protegidas contra limpeza não confirmada.

## Contrato v1

`POST /api/obd_connect/{vehicle_id}/batches`, `Authorization: Bearer <chave exclusiva do receptor>`, `Content-Type: application/json`.

Envelope: `schemaVersion=1`, `batchId` UUID, `vehicleId` UUID e `records`. O servidor limita o corpo a 256 KiB e até 256 registros. Valida veículo, campos, origem REAL, unidades, valores finitos/faixas e timestamps (histórico desde 2000 aceito, futuro limitado a cinco minutos).

- Telemetria: UUID, chave `telemetry:<UUID>`, PID, valor/unidade, capturedAtMs, recordedAtMs, sessão e viagem opcional. IDs são imutáveis.
- Viagem: UUID, horários, status, contagem de telemetria e revisão de conteúdo; chave `trip:<UUID>:<revisão SHA-256>`. Não inclui posição, distância ou velocidade calculadas pelo GPS. Cada revisão é um registro independente no histórico.

Resposta: `schemaVersion`, `batchId`, `accepted` (chaves), `rejected` (chave/motivo genérico), `serverReceivedAtMs`. Confirmações só são construídas após o commit SQLite. Reenvio do mesmo conteúdo confirma a mesma chave; chave repetida com conteúdo distinto é rejeitada. Não se usa apenas o status HTTP 200 para confirmar um lote.

O Android valida identidade e cobertura completa das chaves na resposta antes de alterar o banco. Uma viagem modificada durante a requisição não é confirmada por ACK de revisão anterior. Novos checkpoints recolocam a viagem na fila. Reconfigurar o receptor recoloca registros retidos na fila; registros já removidos pela retenção não são ressuscitados.

## Home Assistant

Um config entry por veículo, configurado pela interface com nome, UUID do aplicativo e chave de 32–128 caracteres ASCII sem espaços. A chave é exclusiva dessa integração/veículo; não é token administrativo do Home Assistant. O endpoint público do componente realiza sua própria autenticação por comparação em tempo constante. Não há controle do carro por esse endpoint.

SQLite em `.storage/obd_connect/<entry_id>.sqlite3` guarda histórico e recibos sem expiração automática nesta primeira entrega. Incluir esse diretório nos backups. Não remover recibos enquanto o cliente puder reenviar os IDs. O tamanho deve ser acompanhado; falha de persistência impede confirmação. Remover a configuração não apaga o histórico privado do disco.

Operações SQLite executam fora do event loop. Cada config entry serializa recebimentos e atualizações de sensores. Há nove sensores de telemetria, separados por PID e vinculados ao veículo, e dois diagnósticos de recepção persistida (contagem de registros únicos e horário do último registro recebido). Estes dois diagnósticos não expiram com a idade das medições. A consulta seleciona o maior capturedAtMs por PID; reenvio de leituras antigas não substitui leituras mais novas. Sem amostra nos últimos três minutos, o sensor fica indisponível; verificação de expiração ocorre a cada 30 s. Isso não interpreta ausência de dados como motor desligado.

O histórico bruto preserva horários originais em armazenamento próprio. Ele não é retroinserido no Recorder como se tivesse sido recebido na hora da medição. Viagens ficam armazenadas, mas a primeira entrega não adiciona interface de consulta/exportação de viagens no Home Assistant. Diagnósticos mostram contagens e tipos, sem chave, coordenadas ou histórico bruto.

## Docker e distribuição

A integração roda dentro do Home Assistant, sem servidor FastAPI/MQTT separado. `docker compose --profile ha run --rm ha-tests` usa imagem oficial 2026.11.0 fixada por digest para testar o servidor HTTP, config flow e sensores reais, isolados da instalação residencial.

`tools/package_integration.py` gera ZIP local com o componente e instruções. Estrutura `custom_components/obd_connect/`, `hacs.json`, documentação/issues públicos, codeowner, marca e workflow de validação estão presentes. A release só deve ser publicada depois das verificações; a inclusão no catálogo público exige solicitação e análise separadas.

Referência de distribuição: https://contributors.home-assistant.io/marketplace/guides/integrations/

## Limites atuais

HTTPS exige certificado confiável pelo Android. Não há exceção para HTTP, certificado autoassinado ou redirecionamento. O acesso externo/VPN/reverse proxy precisa encaminhar o endpoint personalizado com Authorization; funcionamento em qualquer provedor de acesso remoto não foi presumido. Credenciais e endpoint residencial não foram configurados.

O celular armazena a chave em preferências privadas excluídas de backup, sem criptografia Keystore adicional. O Home Assistant guarda a chave no config entry. Tokens não são colocados em logs/mensagens de erro do cliente. O usuário pode desativar o envio preservando a fila. Não foi implementada conexão Bluetooth automática nesta etapa.

Neste repositório está apenas a integração Home Assistant; os componentes Android descritos no contrato pertencem ao projeto HR-V Connect separado.
