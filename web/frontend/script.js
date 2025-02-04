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

async function callInitialFetch() {
    catch_converts = document.getElementById('catch_converts')

    q_string = '?catch_converts='+catch_converts.checked.toString()
    a = await fetch('/initial_fetch_self' + q_string , {
    method: "POST",
    body: '{}',
    headers: {
    'Content-Type': 'application/json'
    }}).then(res => res.json()).then(alert('Success!'));

    fetchQueue()
}

async function fetchQueue() {
    const response = await fetch('/fetch_queue');
    const data = await response.json();
    current = data['current']
    queue = data['in queue']
    //queue = [{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true},{"username":"aaa", "user_id": 1111111, "catch_converts": true}]
    fetch_queue = document.getElementById('fetch_queue_container')

    headers = '<tr><th>User Id</th><th>Username</th><th>Catch Converts?</th><th>Maps Left</th></tr>'

    queue_list = []

    for (let i = 0; i < current.length; i++) {
        queue_list.push('<tr>'+
        '<td>'+String(current[i].username)+'</td>'+
        '<td>'+String(current[i].user_id)+'</td>'+
        '<td>'+String(current[i].catch_converts)+'</td>'+
        '<td>'+String(current[i].num_maps)+'</td></tr>')
    }

    for (let i = 0; i < queue.length; i++) {
        queue_list.push('<tr>'+
        '<td>'+String(queue[i].username)+'</td>'+
        '<td>'+String(queue[i].user_id)+'</td>'+
        '<td>'+String(queue[i].catch_converts)+'</td><td> </td></tr>')
    }

    // console.log(queue_list)
    console.log(headers + String(queue_list))
    fetch_queue.innerHTML = headers + queue_list.join('')
}

fetchQueue()