(function () {
    function csrfToken() {
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        if (match) {
            return decodeURIComponent(match[1]);
        }
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function appendMessage(container, role, text, citations) {
        var item = document.createElement('article');
        item.className = 'rag-chat__message rag-chat__message--' + role;

        var body = document.createElement('div');
        body.className = 'rag-chat__bubble';
        body.textContent = text;
        item.appendChild(body);

        if (citations && citations.length) {
            var list = document.createElement('ol');
            list.className = 'rag-chat__sources';
            citations.forEach(function (citation) {
                var source = document.createElement('li');
                var link = document.createElement('a');
                link.href = citation.source_url || '#';
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = citation.title || 'Fonte';
                source.appendChild(link);
                if (citation.section_reference) {
                    var section = document.createElement('span');
                    section.textContent = ' · ' + citation.section_reference;
                    source.appendChild(section);
                }
                list.appendChild(source);
            });
            item.appendChild(list);
        }

        container.appendChild(item);
        container.scrollTop = container.scrollHeight;
    }

    function errorMessage(payload) {
        if (!payload || typeof payload !== 'object') {
            return '';
        }
        if (payload.detail) {
            return String(payload.detail);
        }
        if (payload.non_field_errors && payload.non_field_errors.length) {
            return String(payload.non_field_errors[0]);
        }
        var fields = Object.keys(payload);
        if (!fields.length) {
            return '';
        }
        var value = payload[fields[0]];
        if (Array.isArray(value) && value.length) {
            return String(value[0]);
        }
        if (value) {
            return String(value);
        }
        return '';
    }

    function init(root) {
        var toggle = root.querySelector('.rag-chat__toggle');
        var close = root.querySelector('.rag-chat__close');
        var panel = root.querySelector('.rag-chat__panel');
        var form = root.querySelector('.rag-chat__form');
        var input = root.querySelector('textarea[name="question"], input[name="question"]');
        var messages = root.querySelector('.rag-chat__messages');
        var endpoint = root.dataset.ragChatEndpoint;
        var sessionId = null;

        if (!form || !input || !messages || !endpoint) {
            return;
        }

        function openPanel() {
            if (!panel || !toggle) {
                return;
            }
            panel.hidden = false;
            panel.setAttribute('aria-hidden', 'false');
            toggle.setAttribute('aria-expanded', 'true');
            input.focus();
        }

        function closePanel(shouldFocus) {
            if (!panel || !toggle) {
                return;
            }
            panel.hidden = true;
            panel.setAttribute('aria-hidden', 'true');
            toggle.setAttribute('aria-expanded', 'false');
            if (shouldFocus !== false) {
                toggle.focus();
            }
        }

        if (toggle && panel) {
            closePanel(false);

            toggle.addEventListener('click', function () {
                if (panel.hidden) {
                    openPanel();
                } else {
                    closePanel();
                }
            });
        }
        if (close) {
            close.addEventListener('click', closePanel);
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var question = input.value.trim();
            if (!question) {
                return;
            }

            appendMessage(messages, 'user', question);
            input.value = '';
            form.classList.add('is-loading');

            var payload = {question: question};
            if (sessionId) {
                payload.session_id = sessionId;
            }

            fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken(),
                },
                body: JSON.stringify(payload),
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json()
                            .catch(function () {
                                return {};
                            })
                            .then(function (payload) {
                                throw new Error(errorMessage(payload) || 'Não foi possível consultar o assistente.');
                            });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    sessionId = payload.session_id || sessionId;
                    appendMessage(messages, 'assistant', payload.answer || 'Sem resposta.', payload.citations || []);
                })
                .catch(function (error) {
                    appendMessage(messages, 'assistant', error.message);
                })
                .finally(function () {
                    form.classList.remove('is-loading');
                    input.focus();
                });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-rag-chat-endpoint]').forEach(init);
    });
})();
