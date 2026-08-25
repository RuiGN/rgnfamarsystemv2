(() => {
    'use strict';

    document.addEventListener('click', (event) => {
        if (!event.target.closest('[data-production-map-print]')) return;
        window.print();
    });
})();
