(function () {
    'use strict';

    var SESSION_KEY = 'rgn-farma-assistant-session-id';

    function csrfToken() {
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        if (match) {
            return decodeURIComponent(match[1]);
        }
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function storedSessionId() {
        try {
            return sessionStorage.getItem(SESSION_KEY);
        } catch (error) {
            return null;
        }
    }

    function storeSessionId(sessionId) {
        try {
            sessionStorage.setItem(SESSION_KEY, String(sessionId));
        } catch (error) {
            // O chat continua funcional quando o armazenamento está indisponível.
        }
    }

    function clearSessionId() {
        try {
            sessionStorage.removeItem(SESSION_KEY);
        } catch (error) {
            // O reset local não deve impedir uma nova conversa.
        }
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
                var label = citation.title || 'Fonte';
                if (citation.url) {
                    var link = document.createElement('a');
                    link.href = citation.url;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = label;
                    source.appendChild(link);
                } else {
                    source.appendChild(document.createTextNode(label));
                }
                if (citation.section_reference) {
                    source.appendChild(
                        document.createTextNode(' · ' + citation.section_reference)
                    );
                }
                list.appendChild(source);
            });
            item.appendChild(list);
        }

        container.appendChild(item);
        container.scrollTop = container.scrollHeight;
    }

    function apiErrorMessage(response, payload) {
        if (response.status === 401 || response.status === 403) {
            return 'Sua sessão não permite usar o assistente. Atualize a página ou solicite acesso.';
        }
        if (response.status === 429) {
            return 'O assistente está recebendo muitas solicitações. Tente novamente em instantes.';
        }
        if (response.status >= 500) {
            return 'O assistente está temporariamente indisponível. Tente novamente.';
        }
        if (payload && payload.detail) {
            return String(payload.detail);
        }
        if (payload && payload.session_id && payload.session_id.length) {
            clearSessionId();
            return String(payload.session_id[0]);
        }
        if (payload && payload.question && payload.question.length) {
            return String(payload.question[0]);
        }
        return 'Não foi possível consultar o assistente.';
    }

    function init(root) {
        var toggle = root.querySelector('.rag-chat__toggle');
        var close = root.querySelector('[data-bs-dismiss="offcanvas"]');
        var panel = root.querySelector('.rag-chat__panel');
        var form = root.querySelector('.rag-chat__form');
        var input = root.querySelector('textarea[name="question"], input[name="question"]');
        var messages = root.querySelector('.rag-chat__messages');
        var status = root.querySelector('[data-rag-chat-status]');
        var retry = root.querySelector('[data-rag-chat-retry]');
        var newConversation = root.querySelector('[data-rag-chat-new]');
        var endpoint = root.dataset.ragChatEndpoint;
        var sessionId = storedSessionId();
        var lastQuestion = '';

        if (!form || !input || !messages || !endpoint) {
            return;
        }

        function setStatus(message) {
            if (status) {
                status.textContent = message || '';
            }
        }

        function setLoading(loading) {
            form.classList.toggle('is-loading', loading);
            input.disabled = loading;
            Array.prototype.forEach.call(form.querySelectorAll('button'), function (button) {
                button.disabled = loading;
            });
            root.setAttribute('aria-busy', loading ? 'true' : 'false');
            if (loading) {
                setStatus('Consultando o manual e preparando a resposta…');
            }
        }

        function submitQuestion(question) {
            lastQuestion = question;
            if (retry) {
                retry.hidden = true;
            }
            appendMessage(messages, 'user', question);
            setLoading(true);

            var payload = {question: question};
            if (sessionId) {
                payload.session_id = Number(sessionId);
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
                    return response.json().catch(function () {
                        return {};
                    }).then(function (payload) {
                        if (!response.ok) {
                            throw new Error(apiErrorMessage(response, payload));
                        }
                        return payload;
                    });
                })
                .then(function (payload) {
                    if (payload.session_id) {
                        sessionId = payload.session_id;
                        storeSessionId(sessionId);
                    }
                    appendMessage(
                        messages,
                        'assistant',
                        payload.answer || 'Sem resposta disponível.',
                        payload.citations || []
                    );
                    setStatus('');
                    lastQuestion = '';
                })
                .catch(function (error) {
                    appendMessage(messages, 'assistant', error.message);
                    setStatus('A consulta falhou. Você pode tentar novamente.');
                    if (retry) {
                        retry.hidden = false;
                    }
                })
                .finally(function () {
                    setLoading(false);
                    input.focus();
                });
        }

        if (
            panel
            && panel.classList.contains('offcanvas')
            && window.bootstrap
            && bootstrap.Offcanvas
        ) {
            var offcanvas = bootstrap.Offcanvas.getOrCreateInstance(panel);
            panel.addEventListener('shown.bs.offcanvas', function () {
                input.focus();
            });
            panel.addEventListener('hidden.bs.offcanvas', function () {
                if (toggle) {
                    toggle.focus();
                }
            });
            if (toggle) {
                toggle.addEventListener('click', function () {
                    offcanvas.show();
                });
            }
            if (close) {
                close.addEventListener('click', function () {
                    offcanvas.hide();
                });
            }
        }
        if (newConversation) {
            newConversation.addEventListener('click', function () {
                sessionId = null;
                lastQuestion = '';
                clearSessionId();
                messages.replaceChildren();
                if (retry) {
                    retry.hidden = true;
                }
                setStatus('Nova conversa iniciada.');
                input.focus();
            });
        }
        if (retry) {
            retry.addEventListener('click', function () {
                if (lastQuestion) {
                    retry.hidden = true;
                    submitQuestion(lastQuestion);
                }
            });
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var question = input.value.trim();
            if (!question) {
                setStatus('Digite uma pergunta antes de enviar.');
                return;
            }
            input.value = '';
            submitQuestion(question);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-rag-chat-endpoint]').forEach(init);
    });
})();
