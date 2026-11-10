# Histórico de versões

## 0.1.0 — 2026-11-10

- Configuração pela interface de um veículo e chave exclusiva por receptor.
- Recebimento autenticado de telemetria e revisões de viagem em lotes.
- Histórico e recibos SQLite duráveis; confirmação após commit e deduplicação de reenvios.
- Nove sensores de telemetria, sem regressão por histórico atrasado e com expiração automática.
- GPS e fontes de simulação excluídos do recebimento.
- Traduções de configuração em português e inglês, marca própria e distribuição por repositório personalizado Marketplace/HACS.
- Testes com Home Assistant 2026.11.0 em Docker e validações de distribuição.

A instalação residencial, o caminho pelo Nabu Casa e o agendamento prolongado do Android ainda precisam de validação de campo. Não há envio de comandos ao carro nem interface de viagens no Home Assistant nesta versão.
