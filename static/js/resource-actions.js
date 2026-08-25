(() => {
    'use strict';

    let dialog = null;
    let dialogBody = null;
    let dialogTitle = null;
    let dialogStatus = null;
    let triggeringElement = null;

    function element(tagName, className) {
        const node = document.createElement(tagName);
        if (className) node.className = className;
        return node;
    }

    function buildDialog() {
        const modal = element('dialog', 'domain-action-dialog');
        modal.setAttribute('aria-labelledby', 'domain-action-dialog-title');

        const shell = element('section', 'domain-action-dialog__shell');
        const accent = element('div', 'domain-action-dialog__accent');
        const header = element('header', 'domain-action-dialog__header');
        dialogTitle = element('h2', 'h5 mb-0');
        dialogTitle.id = 'domain-action-dialog-title';
        const closeButton = element('button', 'btn btn-sm btn-light');
        closeButton.type = 'button';
        closeButton.setAttribute('aria-label', 'Fechar');
        closeButton.textContent = '×';
        closeButton.addEventListener('click', () => modal.close());
        header.append(dialogTitle, closeButton);

        dialogStatus = element('p', 'domain-action-dialog__status');
        dialogStatus.setAttribute('role', 'status');
        dialogStatus.setAttribute('aria-live', 'polite');
        dialogBody = element('div', 'domain-action-dialog__body');
        shell.append(accent, header, dialogStatus, dialogBody);
        modal.append(shell);
        modal.addEventListener('close', () => {
            dialogBody.replaceChildren();
            dialogStatus.textContent = '';
            if (triggeringElement) triggeringElement.focus();
        });
        modal.addEventListener('click', (event) => {
            if (event.target === modal) modal.close();
        });
        modal.addEventListener('submit', submitDialogForm);
        document.body.append(modal);
        return modal;
    }

    function extractForm(markup) {
        const parsed = new DOMParser().parseFromString(markup, 'text/html');
        return parsed.querySelector('[data-action-form]');
    }

    async function openAction(link) {
        triggeringElement = link;
        dialog = dialog || buildDialog();
        dialog.className = `domain-action-dialog domain-action-dialog--${link.dataset.actionTone || 'primary'}`;
        dialog.dataset.actionUrl = link.href;
        dialogTitle.textContent = link.dataset.actionLabel || 'Executar ação';
        dialogStatus.textContent = 'Carregando formulário…';
        dialogBody.replaceChildren();
        dialog.showModal();

        try {
            const response = await fetch(link.href, {credentials: 'same-origin'});
            const markup = await response.text();
            const remoteForm = extractForm(markup);
            if (!response.ok || !remoteForm) throw new Error('Formulário indisponível.');
            const form = document.importNode(remoteForm, true);
            dialogBody.replaceChildren(form);
            dialogStatus.textContent = '';
            form.querySelector('input:not([type="hidden"]), textarea, select, button')?.focus();
        } catch (error) {
            dialogStatus.textContent = error.message || 'Não foi possível carregar o formulário.';
        }
    }

    async function submitDialogForm(event) {
        const form = event.target.closest('[data-action-form]');
        if (!form) return;
        event.preventDefault();
        const submitButton = form.querySelector('[data-action-submit]');
        if (submitButton?.disabled) return;
        if (submitButton) submitButton.disabled = true;
        dialogStatus.textContent = 'Executando ação…';

        try {
            const response = await fetch(dialog.dataset.actionUrl, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
                headers: {'X-Requested-With': 'XMLHttpRequest'},
            });
            if (response.redirected) {
                window.location.assign(response.url);
                return;
            }
            const markup = await response.text();
            const replacement = extractForm(markup);
            if (response.ok && replacement) {
                dialogBody.replaceChildren(document.importNode(replacement, true));
                dialogStatus.textContent = 'Revise os campos indicados.';
                return;
            }
            const parsed = new DOMParser().parseFromString(markup, 'text/html');
            const message = parsed.querySelector('[role="alert"]')?.textContent?.trim();
            dialogStatus.textContent = message || 'A ação não pôde ser executada. Atualize a página.';
        } catch (error) {
            dialogStatus.textContent = error.message || 'Não foi possível executar a ação.';
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    }

    document.addEventListener('click', (event) => {
        const link = event.target.closest('[data-domain-action]');
        if (!link || typeof HTMLDialogElement === 'undefined') return;
        event.preventDefault();
        openAction(link);
    });
})();
