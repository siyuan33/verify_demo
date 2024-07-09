// import config from './config.js'
const config = {
	host: '10.0.30.212',
	port: '22',
	username: 'zghg',
	password: 'Zghgjcrz001'
}
const { host, port, username, password } = config

document.addEventListener('DOMContentLoaded', () => {
	const terminal = new Terminal()
	terminal.open(document.getElementById('terminal'))

	let socket

	function connectToServer() {
		if (socket) {
			socket.close()
		}

		socket = new WebSocket(`ws://${window.location.host}`)

		socket.onopen = () => {
			socket.send(
				JSON.stringify({
					type: 'connect',
					host,
					port,
					username,
					password
				})
			)

			document.getElementById('connectBtn').style.display = 'none'
			document.getElementById('disconnectBtn').style.display = 'block'
		}

		socket.onmessage = (event) => {
			const message = JSON.parse(event.data)
			if (message.type === 'data') {
				terminal.write(message.data)
			} else if (message.type === 'error') {
				alert(message.message)
			}
		}

		terminal.onData((data) => {
			if (socket && socket.readyState === WebSocket.OPEN) {
				socket.send(JSON.stringify({ type: 'input', data }))
			}
		})

		document.getElementById('disconnectBtn').addEventListener('click', () => {
			if (socket) {
				socket.send(JSON.stringify({ type: 'disconnect' }))
				terminal.write('\r\n*** Disconnected from server ***\r\n')
				document.getElementById('connectBtn').style.display = 'block'
				document.getElementById('disconnectBtn').style.display = 'none'
				socket.close()
				socket = null
			}
		})

		socket.onclose = () => {
			terminal.write('\r\n*** Disconnected from server ***\r\n')
			document.getElementById('connectBtn').style.display = 'block'
			document.getElementById('disconnectBtn').style.display = 'none'
		}
	}

	document
		.getElementById('connectBtn')
		.addEventListener('click', connectToServer)

	connectToServer()
})
