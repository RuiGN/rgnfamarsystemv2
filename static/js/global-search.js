(function () {
    'use strict';

    var SEARCH_DELAY_MS = 300;

    function initGlobalSearch() {
        var form = document.querySelector('[data-ui="global-search-form"]');
        var input = document.querySelector('[data-ui="global-search-input"]');
        var clearButton = document.querySelector('[data-ui="global-search-clear"]');
        var resultsContainer = document.querySelector('[data-ui="global-search-results"]');
        if (!form || !input || !clearButton || !resultsContainer) return;

        var debounceTimer = null;
        var controller = null;
        var resultLinks = [];
        var activeIndex = -1;

        function setState(message) {
            var state = document.createElement('p');
            state.className = 'global-search-state';
            state.textContent = message;
            resultsContainer.replaceChildren(state);
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
            resultLinks = [];
            activeIndex = -1;
        }

        function activateResult(index) {
            if (!resultLinks.length) return;
            activeIndex = (index + resultLinks.length) % resultLinks.length;
            resultLinks.forEach(function (link, itemIndex) {
                var isActive = itemIndex === activeIndex;
                link.classList.toggle('is-active', isActive);
                link.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            var activeLink = resultLinks[activeIndex];
            input.setAttribute('aria-activedescendant', activeLink.id);
            activeLink.scrollIntoView({ block: 'nearest' });
        }

        function renderResults(results) {
            if (!results.length) {
                setState('Nenhum registro autorizado encontrado.');
                return;
            }

            var fragment = document.createDocumentFragment();
            resultLinks = results.map(function (result, index) {
                var link = document.createElement('a');
                link.id = 'global-search-result-' + index;
                link.className = 'global-search-result';
                link.href = result.url;
                link.setAttribute('role', 'option');
                link.setAttribute('aria-selected', 'false');

                var icon = document.createElement('span');
                icon.className = 'global-search-result__icon';
                icon.setAttribute('aria-hidden', 'true');
                var iconGlyph = document.createElement('i');
                iconGlyph.className = result.icon || 'feather-file-text';
                icon.appendChild(iconGlyph);

                var content = document.createElement('span');
                content.className = 'global-search-result__content';
                var title = document.createElement('strong');
                title.className = 'global-search-result__title';
                title.textContent = result.title;
                var context = document.createElement('span');
                context.className = 'global-search-result__context';
                context.textContent = result.module + ' → ' + result.type;
                content.append(title, context);

                link.append(icon, content);
                link.addEventListener('mouseenter', function () {
                    activateResult(index);
                });
                fragment.appendChild(link);
                return link;
            });
            resultsContainer.replaceChildren(fragment);
            input.setAttribute('aria-expanded', 'true');
            activeIndex = -1;
        }

        function runSearch() {
            var query = input.value.trim();
            if (query.length < 3) {
                if (controller) controller.abort();
                setState('Digite ao menos três caracteres para pesquisar.');
                return;
            }

            if (controller) controller.abort();
            controller = new AbortController();
            setState('Buscando registros autorizados...');
            var url = new URL(input.dataset.searchUrl, window.location.origin);
            url.searchParams.set('q', query);

            fetch(url, {
                headers: { Accept: 'application/json' },
                signal: controller.signal,
            })
                .then(function (response) {
                    if (!response.ok) throw new Error('search-request-failed');
                    return response.json();
                })
                .then(function (payload) {
                    renderResults(Array.isArray(payload.results) ? payload.results : []);
                })
                .catch(function (error) {
                    if (error.name === 'AbortError') return;
                    setState('A busca está indisponível. Tente novamente.');
                });
        }

        input.addEventListener('input', function () {
            window.clearTimeout(debounceTimer);
            debounceTimer = window.setTimeout(runSearch, SEARCH_DELAY_MS);
        });

        input.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                activateResult(activeIndex + 1);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                activateResult(activeIndex - 1);
            } else if (event.key === 'Enter' && activeIndex >= 0) {
                event.preventDefault();
                resultLinks[activeIndex].click();
            } else if (event.key === 'Escape') {
                input.value = '';
                setState('Digite ao menos três caracteres para pesquisar.');
            }
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            if (activeIndex >= 0) resultLinks[activeIndex].click();
        });

        clearButton.addEventListener('click', function () {
            window.clearTimeout(debounceTimer);
            if (controller) controller.abort();
            input.value = '';
            setState('Digite ao menos três caracteres para pesquisar.');
            input.focus();
        });
    }

    document.addEventListener('DOMContentLoaded', initGlobalSearch);
})();
