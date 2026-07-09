// ── Password toggle (global for onclick attributes) ─────────────────────────
function togPass(inputId, iconId) {
    const $i = $('#' + inputId);
    const isPass = $i.attr('type') === 'password';
    $i.attr('type', isPass ? 'text' : 'password');
    $('#' + iconId).attr('class', isPass ? 'fas fa-eye-slash' : 'fas fa-eye');
}

$(document).ready(function () {

    // ── Helpers ──────────────────────────────────────────────────────────────

    function showForm(id) {
        $(".auth-form").removeClass("active");
        $("#" + id).addClass("active");
        clearAllErrors();
    }

    function toast(msg, type) {
        if (!msg) return;
        const icon = type === 'e' ? 'fa-circle-xmark' : 'fa-circle-check';
        const cls  = type === 'e' ? 'tt tt-e' : 'tt tt-s';
        const $t   = $('<div>').addClass(cls).html(`<i class="fas ${icon}"></i> ${msg}`);
        $('#toasts').append($t);
        setTimeout(() => $t.fadeOut(300, () => $t.remove()), 3200);
    }

    function sErr(inputId, errId, msg) {
        $('#' + inputId).addClass('bad');
        $('#' + errId).find('span').text(msg).end().addClass('on');
    }

    function cErr(inputId, errId) {
        $('#' + inputId).removeClass('bad');
        $('#' + errId).removeClass('on');
    }

    function clearAllErrors() {
        $('.fg-input').removeClass('bad');
        $('.fe').removeClass('on');
    }

    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    // ── Theme toggle ──────────────────────────────────────────────────────────

    $(".theme-toggle-auth").click(function () {
        const isDark = $("html").attr("data-theme") === "dark";
        $("html").attr("data-theme", isDark ? "light" : "dark");
        $("#themeAuthIcon").attr("class", isDark ? "fas fa-sun" : "fas fa-moon");
        $("#themeAuthLabel").text(isDark ? "Light" : "Dark");
    });

    // ── Form navigation ───────────────────────────────────────────────────────

    $("#loginForm .auth-link").last().click(function (e) { e.preventDefault(); showForm("registerForm"); });
    $("#registerForm .auth-link").click(function (e) { e.preventDefault(); showForm("loginForm"); });
    $("#loginForm .auth-link").first().click(function (e) { e.preventDefault(); showForm("forgotEmailForm"); });
    $("#forgotEmailForm .auth-back").click(function (e) { e.preventDefault(); showForm("loginForm"); });
    $("#forgotOtpForm .auth-back").click(function (e) { e.preventDefault(); showForm("forgotEmailForm"); });
    $("#forgotNewPassForm .auth-back").click(function (e) { e.preventDefault(); showForm("forgotOtpForm"); });
    $("#forgotSuccessForm .bl").click(function (e) { e.preventDefault(); showForm("loginForm"); });

    // ── Clear errors on input ─────────────────────────────────────────────────

    $('#lEmail').on('input', function () { cErr('lEmail', 'eErr'); });
    $('#lPass').on('input',  function () { cErr('lPass',  'pErr'); });
    $('#rName').on('input',  function () { cErr('rName',  'rnErr'); });
    $('#rEmail').on('input', function () { cErr('rEmail', 'reErr'); });
    $('#rPass').on('input',  function () { cErr('rPass',  'rpErr'); });
    $('#rPassC').on('input', function () { cErr('rPassC', 'rpcErr'); });

    // ── Login ─────────────────────────────────────────────────────────────────

    $("#loginForm form").submit(function (e) {
        e.preventDefault();
        let ok = true;
        const em = $('#lEmail').val().trim();
        const pw = $('#lPass').val();

        if (!em)                    { sErr('lEmail', 'eErr', 'Email is required');       ok = false; }
        else if (!EMAIL_RE.test(em)){ sErr('lEmail', 'eErr', 'Enter a valid email');     ok = false; }
        if (!pw)                    { sErr('lPass',  'pErr', 'Password is required');    ok = false; }
        if (!ok) return;

        const $btn = $('#lBtn').prop('disabled', true).addClass('ld');

        $.ajax({
            url: '/api/auth/login',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ email: em, password: pw }),

            success: function (res) {
                $btn.prop('disabled', false).removeClass('ld');
                toast(res.message, 's');
                setTimeout(() => window.location.href = res.redirect, 1000);
            },

            error: function (xhr) {
                $btn.prop('disabled', false).removeClass('ld');
                const res = xhr.responseJSON;
                if (res?.show_register) {
                    showForm('registerForm');
                    $('#rEmail').val(em);
                    toast(res.error, 'e');
                } else {
                    toast(res?.error || 'Login failed', 'e');
                }
            }
        });
    });

    // ── Register ──────────────────────────────────────────────────────────────

    $("#registerForm form").submit(function (e) {
        e.preventDefault();
        let ok = true;
        const nm  = $('#rName').val().trim();
        const em  = $('#rEmail').val().trim();
        const pw  = $('#rPass').val();
        const pwc = $('#rPassC').val();

        if (!nm || nm.length < 2)   { sErr('rName',  'rnErr',  'Name must be at least 2 characters'); ok = false; }
        if (!em)                    { sErr('rEmail', 'reErr',  'Email is required');                  ok = false; }
        else if (!EMAIL_RE.test(em)){ sErr('rEmail', 'reErr',  'Enter a valid email');                ok = false; }
        if (!pw || pw.length < 6)   { sErr('rPass',  'rpErr',  'Min 6 characters');                  ok = false; }
        if (!pwc)                   { sErr('rPassC', 'rpcErr', 'Please confirm password');            ok = false; }
        else if (pw !== pwc)        { sErr('rPassC', 'rpcErr', 'Passwords do not match');             ok = false; }
        if (!$('#rAgree').is(':checked')) { toast('Please agree to the Terms of Service', 'e'); ok = false; }
        if (!ok) return;

        const $btn = $('#rBtn').prop('disabled', true).addClass('ld');

        $.ajax({
            url: '/api/auth/register',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ name: nm, email: em, password: pw, confirm_password: pwc, agree: true }),

            success: function (res) {
                $btn.prop('disabled', false).removeClass('ld');
                toast(res.message);
                $('#rName, #rEmail, #rPass, #rPassC').val('');
                $('#rAgree').prop('checked', false);
                setTimeout(() => showForm('loginForm'), 1500);
            },

            error: function (xhr) {
                $btn.prop('disabled', false).removeClass('ld');
                toast(xhr.responseJSON?.error || 'Registration failed', 'e');
            }
        });
    });

});
