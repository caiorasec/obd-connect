# Instalar e parear OBD Connect

Versão inicial: integração 0.1.1, Android 0.4.0. Testada com Home Assistant 2026.11.0 em Docker. A versão residencial ainda precisa ser informada e validada. Nenhum endereço/credencial residencial foi configurado.

## Instalação local

1. Gere o pacote com `python3 tools/package_integration.py`.
2. Extraia `artifacts/obd-connect-0.1.1.zip` e copie a pasta `custom_components/obd_connect` para `<config>/custom_components/obd_connect` do Home Assistant. Em HA Container, `<config>` é o volume montado em `/config`.
3. Reinicie o Home Assistant para reconhecer a instalação manual.
4. Abra Configurações → Dispositivos e serviços → Adicionar integração → OBD Connect.

## Marketplace / HACS

Adicione `https://github.com/caiorasec/obd-connect` como repositório personalizado, categoria Integração, ou use [o botão de instalação](https://my.home-assistant.io/redirect/hacs_repository/?owner=caiorasec&repository=obd-connect&category=integration). Instale OBD Connect e siga a indicação de reinício da sua versão. A inclusão no catálogo público de busca é uma etapa separada; não é necessária para instalar por esse link.

## Pareamento

1. No Android 0.4.0, abra Ajustes → OBD Connect. O envio está desativado por padrão.
2. Copie o UUID mostrado; se ainda não existe, faça uma sessão de coleta para criar o veículo.
3. Toque Gerar chave e Copiar chave. Guarde a chave apenas nos dois lados; ela dá acesso ao receptor daquele veículo.
4. Na integração do Home Assistant, informe nome, o UUID e essa mesma chave.
5. No Android, informe somente a URL HTTPS base do Home Assistant, sem `/api` ou outro caminho, usuário ou parâmetros. Use certificado válido. O aplicativo não aceita HTTP nem segue redirecionamentos.
6. Toque Salvar e habilitar envio. Depois, Enviar lote agora permite validar um lote sem ligar o carro.

Salvar um novo pareamento recoloca registros ainda retidos na fila. O receptor deduplica reenvios. Desativar envio mantém o histórico e os dados pendentes no celular.

Para trocar a chave do receptor nesta primeira versão, remova e adicione a integração com o mesmo UUID e a nova chave; confirme backup do histórico antes. O novo config entry usa outro arquivo de histórico. Salve a nova configuração no Android para reenviar os dados retidos. Rotação pela interface sem recriar a entrada fica para uma próxima versão.

## Funcionamento

- Durante coleta REAL: um lote a cada 60 s; todas as leituras salvas podem ser enviadas, sem reduzir a frequência de coleta.
- Fora da coleta: WorkManager tenta enviar com rede, em horários definidos pelo Android. Não é um temporizador exato de um minuto.
- Sem acesso ao servidor: fila preservada, novas tentativas com atraso progressivo.
- GPS: não enviado, mesmo que já existam posições na fila local. Os registros permanecem protegidos.
- Leituras de simulação: não enviadas. Se o envio estiver habilitado, o agendador pode enviar pendências reais antigas enquanto a interface mostra uma simulação; elas continuam com sua origem real.
- Sensores: RPM, velocidade, arrefecimento, carga, acelerador, MAP, temperatura de admissão, tensão do módulo e tensão ATRV. Leituras com mais de três minutos ficam indisponíveis. Enviar as viagens antigas não torna seus valores atuais.

## Rede, histórico e diagnóstico

Para envio por dados móveis, a URL precisa ser acessível fora de casa (ou por VPN). Ter internet não basta se o Home Assistant estiver disponível apenas na LAN. O proxy deve permitir `POST /api/obd_connect/<UUID>/batches` e preservar Authorization. Validar compatibilidade antes de usar qualquer solução de acesso remoto.

Dados/recibos ficam em `<config>/.storage/obd_connect/`; inclua nos backups. O histórico não é apagado ao remover o config entry. Não apague recibos de deduplicação enquanto o celular puder reenviá-los. Não há expurgo automático do histórico no servidor nessa versão.

A tela do Android informa confirmação, rejeição ou fila preservada. HTTP 401 geralmente indica UUID/chave/entrada não carregada; falhas de conexão podem indicar URL, certificado ou acesso ao proxy. O app oculta detalhes de erro que poderiam expor credenciais. Uma resposta válida não garante que todos os registros foram aceitos: confira rejeitados e pendências. Detalhes das viagens ainda são consultados no Android.

## Desenvolvimento

```bash
docker compose --profile ha run --rm ha-tests
python3 tools/package_integration.py
```

Os testes usam apenas dados fictícios em ambiente temporário. Não iniciam conexão com o carro, não usam credenciais residenciais e não limpam a fila do telefone.

## Recebeu dados, mas a telemetria está indisponível?

No dispositivo OBD Connect, consulte os diagnósticos **Registros recebidos** e **Último registro recebido** (integração 0.1.1+). Eles mostram registros persistidos, mesmo que a medição seja antiga. Os nove sensores de telemetria só ficam disponíveis com amostras dos últimos três minutos.

A simulação do aplicativo não transmite valores fictícios ao Home Assistant. É possível enviar o histórico real já guardado sem ligar o carro; isso atualiza os diagnósticos e o histórico, mas não transforma leituras antigas em medições atuais. GPS pendente permanece local.
