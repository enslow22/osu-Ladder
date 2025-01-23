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
    }});
    window.location.href = "/";
}

function callInitialFetch(apikey) {
    osu = document.getElementById('osu')
    taiko = document.getElementById('taiko')
    fruits = document.getElementById('fruits')
    mania = document.getElementById('mania')
    console.log([osu.checked, taiko.checked, fruits.checked, mania.checked])
    arr = [osu.checked, taiko.checked, fruits.checked, mania.checked]
    mapper = ['osu', 'taiko', 'fruits', 'mania']
    modes = []
    for (let i = 0; i < arr.length; i++) {
        if (arr[i]) {
            modes.push(mapper[i])
        }
    }
    // Send a request to the api with the user's api key and the modes

    return modes
}
