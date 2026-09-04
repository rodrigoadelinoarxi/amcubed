# ARXI Certification Patch - Local Signing Module

## Descrição

Este módulo permite a assinatura local de documentos fiscais portugueses sem necessidade de obter o hash remotamente, mantendo a validação da instância ARXI.

## Características

- ✅ **Assinatura Local RSA**: Usa a chave privada local para assinar documentos
- ✅ **Validação de Instância**: Mantém o controlo `contract.instance.status` - a instância tem que estar válida
- ✅ **Certificados Incluídos**: Todos os certificados necessários estão no módulo
- ✅ **Compatibilidade Total**: Funciona com l10n_pt_certificate sem conflitos
- ✅ **Fallback Automático**: Se os certificados não forem encontrados, usa os originais do l10n_pt_certificate

## Ficheiros Modificados

Este módulo faz override dos seguintes modelos:

### 1. `account_mixin.py`
- Override do método `compute_hash()` para assinatura local
- Override do método `encode_hash()` para usar chave privada local
- Override do método `_get_private_key()` para usar certificados deste módulo
- **Validação de instância adicionada** antes de assinar

### 2. `account_move.py`
- Override do método `_compute_hash()` para assinatura local
- Override do método `_get_private_key()` para usar certificados deste módulo
- **Validação de instância adicionada** antes de assinar

### 3. `at_webservice_mixin.py`
- Override do método `at_ws_communication()` para usar certificados locais
- **Validação de instância adicionada** antes de comunicar com webservices AT
- Suporte para certificados de produção e teste

## Certificados Incluídos

```
certificates/
├── certificate.pem           # Certificado de produção
├── test_certificate.pem      # Certificado de teste
├── priv_key.pem             # Chave privada para assinatura
├── public_key.pem           # Chave pública para webservices
└── test_public_key.pem      # Chave pública de teste
```

## Instalação

1. Copiar o módulo para o diretório de addons do Odoo
2. Atualizar a lista de módulos
3. Instalar o módulo `ARXI_CERTIFICATION_PATCH`

```bash
# Copiar módulo
cp -r ARXI_CERTIFICATION_PATCH /path/to/odoo/addons/

# No Odoo
# Apps > Update Apps List
# Apps > Search "ARXI Certification Patch" > Install
```

## Dependências

- `l10n_pt_certificate` - Módulo base de certificação portuguesa

## Validação de Instância

O módulo mantém a validação de instância ARXI em **todos os pontos críticos**:

```python
# Validação executada antes de:
# 1. Assinar hash de documento (compute_hash)
# 2. Calcular hash de fatura (_compute_hash)
# 3. Comunicar com webservices AT (at_ws_communication)

instance_status = self.env['contract.instance.status'].sudo()
if instance_status.check_instance_blocked():
    block_message = instance_status.get_block_message()
    _logger.warning(f'Event blocked for user {self.env.uid}: {block_message}')
    raise AccessDenied(block_message)
```

## Fluxo de Assinatura

### Antes (Remoto):
```
Documento → Validar Instância → Obter Hash Remoto → Assinar → Guardar
```

### Depois (Local):
```
Documento → Validar Instância → Assinar Localmente com RSA → Guardar
```

## Compatibilidade

- ✅ Odoo 18.0
- ✅ l10n_pt_certificate
- ✅ l10n_pt_ao
- ✅ ARXI_CERTIFICATION (módulos ofuscados)

## Notas de Segurança

- ⚠️ As chaves privadas estão incluídas no módulo - **use apenas em ambientes controlados**
- ✅ A validação de instância garante que apenas instâncias válidas podem assinar documentos
- ✅ O módulo não remove nenhuma validação de segurança, apenas altera o método de assinatura

## Logs

O módulo regista informação detalhada em diferentes níveis:

- **DEBUG**: Hashes gerados e documentos assinados
- **INFO**: Valores a serem hasheados e comunicações webservice
- **WARNING**: Fallback para certificados originais, instâncias bloqueadas

## Resolução de Problemas

### Erro: "Private key not found"
- Verificar que o módulo está instalado corretamente
- Verificar permissões dos ficheiros em `certificates/`
- O módulo fará fallback automático para `l10n_pt_certificate/priv_key.pem`

### Erro: "Hash control not found"
- Configurar o parâmetro de sistema `hash.control`
- Menu: Settings → Technical → Parameters → System Parameters

### Erro: "Event blocked for user X"
- A instância está bloqueada ou inválida
- Contactar suporte ARXI para validar a instância

## Autor

**ARXI** - https://arxi.pt

## Licença

LGPL-3
