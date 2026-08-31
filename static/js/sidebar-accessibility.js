(function () {
    function toggleMenu(button) {
        var item = button.closest('.nxl-hasmenu');
        var controls = button.getAttribute('aria-controls');
        var submenu = controls ? document.getElementById(controls) : null;
        var expanded = button.getAttribute('aria-expanded') === 'true';

        button.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        if (item) {
            item.classList.toggle('nxl-trigger', !expanded);
        }
        if (submenu) {
            submenu.hidden = expanded;
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.sidebar-menu-toggle[aria-controls]').forEach(function (button) {
            var submenu = document.getElementById(button.getAttribute('aria-controls'));
            if (submenu) {
                submenu.hidden = button.getAttribute('aria-expanded') !== 'true';
            }
            button.addEventListener('click', function (event) {
                event.stopPropagation();
                toggleMenu(button);
            });
        });
    });
})();
