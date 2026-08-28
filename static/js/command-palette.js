(function () {
    'use strict';

    function initCommandPalette() {
        var modalElement = document.getElementById('command-palette-modal');
        var input = document.querySelector('[data-command-palette-input]');
        var resultsContainer = document.querySelector('[data-command-palette-results]');
        if (!modalElement || !input || !resultsContainer || !window.bootstrap) return;

        var modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
        var commandsByUrl = new Map();
        document.querySelectorAll('[data-command-label][data-command-url]').forEach(function (link) {
            var label = link.dataset.commandLabel.trim();
            var url = link.dataset.commandUrl.trim();
            if (label && url && !commandsByUrl.has(url)) {
                commandsByUrl.set(url, { label: label, url: url });
            }
        });
        var commands = Array.from(commandsByUrl.values());
        var resultButtons = [];
        var activeIndex = -1;

        function setActive(index) {
            if (!resultButtons.length) return;
            activeIndex = (index + resultButtons.length) % resultButtons.length;
            resultButtons.forEach(function (button, itemIndex) {
                var isActive = itemIndex === activeIndex;
                button.classList.toggle('is-active', isActive);
                button.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            resultButtons[activeIndex].scrollIntoView({ block: 'nearest' });
        }

        function renderCommands() {
            var query = input.value.trim().toLocaleLowerCase('pt-BR');
            var visibleCommands = commands.filter(function (command) {
                return !query || command.label.toLocaleLowerCase('pt-BR').includes(query);
            });

            if (!visibleCommands.length) {
                var empty = document.createElement('p');
                empty.className = 'command-palette__empty';
                empty.textContent = 'Nenhum destino autorizado encontrado.';
                resultsContainer.replaceChildren(empty);
                resultButtons = [];
                activeIndex = -1;
                return;
            }

            var fragment = document.createDocumentFragment();
            resultButtons = visibleCommands.map(function (command, index) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'command-palette__command';
                button.setAttribute('role', 'option');
                button.setAttribute('aria-selected', 'false');

                var label = document.createElement('span');
                label.className = 'command-palette__label';
                label.textContent = command.label;
                var hint = document.createElement('span');
                hint.className = 'command-palette__hint';
                hint.textContent = 'Abrir';
                button.append(label, hint);
                button.addEventListener('mouseenter', function () {
                    setActive(index);
                });
                button.addEventListener('click', function () {
                    window.location.assign(command.url);
                });
                fragment.appendChild(button);
                return button;
            });
            resultsContainer.replaceChildren(fragment);
            activeIndex = -1;
        }

        function openPalette() {
            modal.show();
        }

        document.querySelectorAll('[data-command-palette-open]').forEach(function (trigger) {
            trigger.addEventListener('click', openPalette);
        });

        document.addEventListener('keydown', function (event) {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                openPalette();
            }
        });

        input.addEventListener('input', renderCommands);
        input.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                setActive(activeIndex + 1);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setActive(activeIndex - 1);
            } else if (event.key === 'Enter' && activeIndex >= 0) {
                event.preventDefault();
                resultButtons[activeIndex].click();
            } else if (event.key === 'Escape') {
                modal.hide();
            }
        });

        modalElement.addEventListener('shown.bs.modal', function () {
            input.value = '';
            renderCommands();
            input.focus();
        });
    }

    document.addEventListener('DOMContentLoaded', initCommandPalette);
})();
