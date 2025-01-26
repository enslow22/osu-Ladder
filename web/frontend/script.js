function submit() {
    alert("hi")
}

function getCookie() {
    value_or_null = (document.cookie.match(/^(?:.*;)?\s*session\s*=\s*([^;]+)(?:.*)?$/)||[,null])[1]
    console.log(value_or_null)
}

function login() {
    // Move to login
    window.location.href = "/login";
}

async function fetchAsync(url) {
    let response = await fetch(url);
    let data = await response.json();
    return data;
}

async function logout() {
    a = await fetch('/logout', {
    method: "POST",
    body: '{}',
    headers: {
    'Content-Type': 'application/json'
    }}).then(() => {window.location.href = "/"});
}

async function callInitialFetch(apikey) {
    catch_converts = document.getElementById('catch_converts')

    q_string = '?catch_converts='+catch_converts.value.toString()
    console.log(q_string)
    a = await fetch('/initial_fetch_self' + q_string , {
    method: "POST",
    body: '{}',
    headers: {
    'Content-Type': 'application/json'
    }});
    return a
}
