:target: https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps
:alt: License: Odoo Proprietary License v1.0

==================
EuPago Integration
==================

Pagamentos podem agora ser feitos via Multibanco / MBWay / Cartão de Crédito através da api EuPago.

Installation
============

To install this module, you need to:

#. Download the module from the odoo app store
#. Unzip to the addons path
#. Install module in Odoo Community 14 or Enterprise 14

Known issues / Roadmap
======================

Problemas:
#. Estes métodos de pagamento devem ser usados apenas para vendas na moeda "euro" (€)

Para usar os métodos de pagamento facultados pela EuPago deve:

#. Registar-se no website da Eupago (https://www.eupago.pt)
#. Após o Registo deve ir a "Conta", "Listagem de Canais", e editar o canal desejado, já na edição do canal, selecionar a opção "Receber notificação para um url"
#. Definir a Url para "O_SEU_DOMINIO/payment/eupago/notify?token=CHAVE_PRIVADA_À_SUA_ESCOLHA"
#. Definir o Nome da variável GET que recebe o valor para 'valor'
#. Definir o Nome da variável GET que recebe a identificação do canal para 'canal'
#. Definir o Nome da variável GET que recebe a referência para 'referencia'
#. Definir o Nome da variável GET que recebe a transação para 'transacao'
#. Definir o Nome da variável GET que recebe a o identificador da encomenda para 'identificador'
#. Após a instalação do módulo no Odoo, deve ativar o modo de programador nas configurações
#. Já em modo de programador deve ir à aplicação "Web Site", Configurações, Intermediários de Pagamento
#. No método "EuPago MBWay" deve inserir a Chave privada que escolheu, e inseriu na url de callback
#. No método "EuPago Referência multibanco" deve inserir também a mesma chave privada do passo anterior
#. No método "EuPago Referência multibanco" deve definir também o némero de dias que uma referência multibanco deve ser válida (entre 1 e 30 dias)

Credits
=======

Images
------
* Icons made by Vectors Market from Flaticon is licensed by Creative Commons BY 3.0

Contributors
------------

* Marcelo Pereira <marcelo.pereira@arxi.pt> (geral@arxi.pt)
* Nuno Silva <nuno.silva@arxi.pt> (geral@arxi.pt)
* Tiago Santos <tiago.santos@arxi.pt> (geral@arxi.pt)

Do not contact contributors directly about support or help with technical issues.

License
=======
Odoo Proprietary License v1.0

This software and associated files (the "Software") may only be used (executed, modified, executed after modifications) if you have purchased a valid license from the authors, typically via Odoo Apps, or if you have received a written agreement from the authors of the Software (see the COPYRIGHT file).

You may develop Odoo modules that use the Software as a library (typically by depending on it, importing it and using its resources), but without copying any source code or material from the Software. You may distribute those modules under the license of your choice, provided that this license is compatible with the terms of the Odoo Proprietary License (For example: LGPL, MIT, or proprietary licenses similar to this one).

It is forbidden to publish, distribute, sublicense, or sell copies of the Software or modified copies of the Software.

The above copyright notice and this permission notice must be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
