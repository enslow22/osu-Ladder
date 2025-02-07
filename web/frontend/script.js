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
    a = await fetch('/fetch/enqueue_self' + q_string , {
    method: "POST",
    body: '{}',
    headers: {
    'Content-Type': 'application/json'
    }}).then(res => res.json()).then(data => alert(data['message']));

    fetchQueue()
}

async function fetchQueue() {
    const response = await fetch('/fetch/queue');
    const data = await response.json();
    current = data['current']
    queue = data['in queue']
    fetch_queue = document.getElementById('fetch_queue_container')

    headers = '<tr><th>Username</th><th>User Id</th><th>Catch Converts?</th><th>Progress</th></tr>'

    queue_list = []

    for (let i = 0; i < current.length; i++) {
        total_maps = current[i].total_maps
        finished_maps = current[i].total_maps - current[i].num_maps
        queue_list.push('<tr>'+
        '<td>'+String(current[i].username)+'</td>'+
        '<td>'+String(current[i].user_id)+'</td>'+
        '<td>'+String(current[i].catch_converts)+'</td>'+
        '<td>'+String(finished_maps)+' / '+String(total_maps)+' ('+parseFloat( finished_maps / total_maps * 100).toFixed(2)+'%)'+'</td></tr>')
    }

    for (let i = 0; i < queue.length; i++) {
        queue_list.push('<tr>'+
        '<td>'+String(queue[i].username)+'</td>'+
        '<td>'+String(queue[i].user_id)+'</td>'+
        '<td>'+String(queue[i].catch_converts)+'</td><td> </td></tr>')
    }

    fetch_queue.innerHTML = headers + queue_list.join('')
}