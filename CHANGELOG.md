# Histórico de versões

## 0.1.1 — 2026-11-10

- Acrescenta diagnósticos Registros recebidos e Último registro recebido, inclusive quando todas as leituras do veículo já são antigas.
- Contador e horário são restaurados do histórico persistido; reenvios idênticos não aumentam a contagem.
- Mantém os nove sensores de telemetria indisponíveis após três minutos e não envia simulações nem GPS.
- Torna a sincronização visível sem exigir nova coleta ou ligar o carro.

## 0.1.0 — 2026-11-10

- Configuração pela interface de um veículo e chave exclusiva por receptor.
- Recebimento autenticado de telemetria e revisões de viagem em lotes.
- Histórico e recibos SQLite duráveis; confirmação após commit e deduplicação de reenvios.
- Nove sensores de telemetria, sem regressão por histórico atrasado e com expiração automática.
- GPS e fontes de simulação excluídos do recebimento.
- Traduções de configuração em português e inglês, marca própria e distribuição por repositório personalizado Marketplace/HACS.
- Licença MIT e autoria pública pelo perfil GitHub, com e-mail noreply.
- Testes com Home Assistant 2026.11.0 em Docker e validações de distribuição.

A instalação residencial, o caminho pelo Nabu Casa e o agendamento prolongado do Android ainda precisam de validação de campo. Não há envio de comandos ao carro nem interface de viagens no Home Assistant nesta versão.
