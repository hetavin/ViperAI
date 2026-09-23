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

    function showFormNav(id) {
        showForm(id);
        const url = new URL(window.location);
        if (id === 'registerForm') url.searchParams.set('mode', 'register');
        else url.searchParams.delete('mode');
        history.replaceState(null, '', url);
    }

    // Show register form if mode=register (set by server via data attribute)
    if ($('#authScreen').data('mode') === 'register') {
        showForm('registerForm');
    }

    $("#loginForm .auth-link").last().click(function (e) { e.preventDefault(); showFormNav("registerForm"); });
    $("#registerForm .auth-link").click(function (e) { e.preventDefault(); showFormNav("loginForm"); });
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
                setTimeout(() => {
                    history.replaceState(null, '', res.redirect);
                    window.location.replace(res.redirect);
                }, 1000);
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
                setTimeout(() => showFormNav('loginForm'), 1500);
            },

            error: function (xhr) {
                $btn.prop('disabled', false).removeClass('ld');
                toast(xhr.responseJSON?.error || 'Registration failed', 'e');
            }
        });
    });


    // ── Forgot password ───────────────────────────────────────────────────────
    // The three forms below call these from their onsubmit attributes, so they
    // have to be reachable from the global scope — they were never defined at
    // all, which made "Send Verification Code" throw and reload the page.

    let fpEmail = '';
    let resendTimer = null;

    function stopResendTimer() {
        if (resendTimer) { clearInterval(resendTimer); resendTimer = null; }
    }

    function startResendTimer(seconds) {
        stopResendTimer();
        let left = seconds;
        const $btn = $('#resendBtn');
        const paint = () => $btn.html('Resend in <span id="resendTimer">' + left + '</span>s');
        $btn.prop('disabled', true);
        paint();
        resendTimer = setInterval(() => {
            left -= 1;
            if (left <= 0) {
                stopResendTimer();
                $btn.prop('disabled', false).text('Resend code');
                return;
            }
            paint();
        }, 1000);
    }

    function otpValue() {
        return $('.otp-box').map(function () { return (this.value || '').trim(); }).get().join('');
    }

    function clearOtp() {
        $('.otp-box').val('').removeClass('bad');
        $('#otpErr').removeClass('on');
        $('.otp-box').first().focus();
    }

    // Typing / pasting across the six boxes
    $('#otpWrap').on('input', '.otp-box', function () {
        this.value = (this.value || '').replace(/\D/g, '').slice(0, 1);
        $('#otpErr').removeClass('on');
        if (this.value) $(this).next('.otp-box').focus();
    });

    $('#otpWrap').on('keydown', '.otp-box', function (e) {
        if (e.key === 'Backspace' && !this.value) $(this).prev('.otp-box').focus();
        if (e.key === 'ArrowLeft') $(this).prev('.otp-box').focus();
        if (e.key === 'ArrowRight') $(this).next('.otp-box').focus();
    });

    $('#otpWrap').on('paste', '.otp-box', function (e) {
        const text = (e.originalEvent.clipboardData || window.clipboardData).getData('text') || '';
        const digits = text.replace(/\D/g, '').slice(0, 6);
        if (!digits) return;
        e.preventDefault();
        const $boxes = $('.otp-box');
        $boxes.val('');
        digits.split('').forEach((d, i) => $boxes.eq(i).val(d));
        $boxes.eq(Math.min(digits.length, 5)).focus();
    });

    $('#fpEmail').on('input', function () { cErr('fpEmail', 'fpEErr'); });
    $('#fpNewPass').on('input', function () { cErr('fpNewPass', 'fnpErr'); });
    $('#fpConfPass').on('input', function () { cErr('fpConfPass', 'fcpErr'); });

    function sendOtpRequest(email, $btn, onSent) {
        $btn.prop('disabled', true).addClass('ld');
        $.ajax({
            url: '/api/auth/forgot/send',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ email: email }),

            success: function (res) {
                $btn.prop('disabled', false).removeClass('ld');
                fpEmail = email;
                $('#fpOtpEmail').text(email);
                toast(res.message || 'Verification code sent', 's');
                onSent && onSent();
            },

            error: function (xhr) {
                $btn.prop('disabled', false).removeClass('ld');
                toast(xhr.responseJSON?.error || 'Could not send the code', 'e');
            }
        });
    }

    window.doSendOtp = function (e) {
        e.preventDefault();
        const em = $('#fpEmail').val().trim();

        if (!em) { sErr('fpEmail', 'fpEErr', 'Email is required'); return; }
        if (!EMAIL_RE.test(em)) { sErr('fpEmail', 'fpEErr', 'Enter a valid email'); return; }

        sendOtpRequest(em, $('#fpSendBtn'), function () {
            showForm('forgotOtpForm');
            clearOtp();
            startResendTimer(30);
        });
    };

    window.resendOtp = function () {
        if (!fpEmail) { showForm('forgotEmailForm'); return; }
        sendOtpRequest(fpEmail, $('#resendBtn'), function () {
            clearOtp();
            startResendTimer(30);
        });
    };

    window.doVerifyOtp = function (e) {
        e.preventDefault();
        const code = otpValue();

        if (code.length !== 6) {
            $('.otp-box').addClass('bad');
            $('#otpErr').find('span').text('Enter all 6 digits').end().addClass('on');
            return;
        }

        const $btn = $('#fpVerifyBtn').prop('disabled', true).addClass('ld');

        $.ajax({
            url: '/api/auth/forgot/verify',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ email: fpEmail, code: code }),

            success: function () {
                $btn.prop('disabled', false).removeClass('ld');
                stopResendTimer();
                $('#fpNewPass, #fpConfPass').val('');
                showForm('forgotNewPassForm');
            },

            error: function (xhr) {
                $btn.prop('disabled', false).removeClass('ld');
                const msg = xhr.responseJSON?.error || 'Verification failed';
                $('.otp-box').addClass('bad');
                $('#otpErr').find('span').text(msg).end().addClass('on');
            }
        });
    };

    window.doResetPassword = function (e) {
        e.preventDefault();
        const pw = $('#fpNewPass').val();
        const pwc = $('#fpConfPass').val();
        let ok = true;

        if (!pw || pw.length < 6) { sErr('fpNewPass', 'fnpErr', 'Min 6 characters'); ok = false; }
        if (!pwc) { sErr('fpConfPass', 'fcpErr', 'Please confirm password'); ok = false; }
        else if (pw !== pwc) { sErr('fpConfPass', 'fcpErr', 'Passwords do not match'); ok = false; }
        if (!ok) return;

        const $btn = $('#fpResetBtn').prop('disabled', true).addClass('ld');

        $.ajax({
            url: '/api/auth/forgot/reset',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ password: pw, confirm_password: pwc }),

            success: function (res) {
                $btn.prop('disabled', false).removeClass('ld');
                $('#fpNewPass, #fpConfPass, #fpEmail').val('');
                clearOtp();
                toast(res.message || 'Password changed', 's');
                showForm('forgotSuccessForm');
            },

            error: function (xhr) {
                $btn.prop('disabled', false).removeClass('ld');
                toast(xhr.responseJSON?.error || 'Could not change the password', 'e');
            }
        });
    };

});
