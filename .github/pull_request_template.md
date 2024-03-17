<img src="https://www.byxcapital.com.br/logo_byx.png" width=25% align="right"/>
<br>
<br>
<br>

<h1 align="center"> Título das suas modificações </h1>

# O que foi feito? 🤔
 Neste espaço, escreva um resumo do que foi feito nesse PR, podendo listar libs implementadas e outras informações relevantes para quem estará avaliando seu código entenda todo o contexto.

Caso exista, faça o link da(s) issue(s) relacionada(s) à mudança.

# Como testar o que foi feito? 🔍
Descreva abaixo o passo-a-passo para validar as mudanças. <br>
Caso exista alguma configuração específica, também coloque na descrição, por exemplo:
- Cadastrar um usuário
- Adicionar produto ao carrinho
- Realizar checkout

# Necessidade extra da funcionalidade 🔍
- Parâmetro precisa ser configurado no ambiente?
- Tem variável de ambiente no ENV.?

# Impacto 🔍
- Quais produtos?
- Funcionalidades?
- Necessidade de teste regressivo?

# Checklist de Clean Code 🧹
Certifique-se de que seu PR segue estas práticas de clean code:

- [ ] **Nomes Significativos:** Todas as classes, funções, variáveis e constantes têm nomes claros e significativos.
- [ ] **Funções Pequenas e Focadas:** Cada função é pequena e realiza apenas uma tarefa específica.
- [ ] **Código Autoexplicativo:** O código é legível e fácil de entender sem a necessidade de comentários excessivos.
- [ ] **Tratamento de Erros:** Os erros são tratados de forma adequada e não há presença de código morto ou comentado.
- [ ] **Código DRY (Don't Repeat Yourself):** Não há duplicação de código; a reutilização é aplicada quando apropriado.
- [ ] **Testes Unitários:** Foram escritos testes unitários para as novas funcionalidades ou alterações.
- [ ] **Refatoração:** O código existente foi melhorado sem alterar seu comportamento.
- [ ] **Documentação:** Mudanças significativas estão documentadas (se aplicável).
- [ ] **Padrões de Código:** O código segue os padrões de codificação estabelecidos pelo projeto.

---

# Checklist de Release-Managment
Certifique-se de que seu PR inclue dados para Subida de produção:

- [ ] **Change log:** Preencher o arquivo de changelog com as features presentes no PR.
- [ ] **Feature Flag:** Para a branch de develop e release as features devem ter flags para não execução em produção. Uma vez testada deverá ser removida para ir a main.
- [ ] **Descrição de Risco de Impacto:** respondida a pergunta de impacto na descrição.

---

Lembre-se de marcar cada item ao concluir. Isso ajuda os revisores a entenderem as práticas de clean code que você seguiu.

# Informações adicionais 🗺️
Anexe aqui: diagramas, screenshots, gifs, vídeos, textos ou quaisquer outros conteúdos que ache relevante.
