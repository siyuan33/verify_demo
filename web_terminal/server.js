const express = require('express')
const http = require('http')
const WebSocket = require('ws')
const { Client } = require('ssh2')

const app = express()
const server = http.createServer(app)
const wss = new WebSocket.Server({ server })

app.use(express.static('public'))

wss.on('connection', (ws) => {
	let conn
	let stream

	ws.on('message', (msg) => {
		const data = JSON.parse(msg)
		if (data.type === 'connect') {
			conn = new Client()
			conn
				.on('ready', () => {
					conn.shell((err, sshStream) => {
						if (err) {
							ws.send(JSON.stringify({ type: 'error', message: err.message }))
							return
						}
						stream = sshStream
						stream.on('data', (data) => {
							ws.send(JSON.stringify({ type: 'data', data: data.toString() }))
						})
						ws.on('message', (msg) => {
							const data = JSON.parse(msg)
							if (data.type === 'input' && stream) {
								stream.write(data.data)
							}
						})
						stream.on('close', () => {
							conn.end()
							ws.close()
						})
					})
				})
				.connect({
					host: data.host,
					port: data.port,
					username: data.username,
					password: data.password
				})
		} else if (data.type === 'disconnect') {
			if (conn) {
				conn.end()
			}
		}
	})

	ws.on('close', () => {
		if (stream) {
			stream.end()
		}
		if (conn) {
			conn.end()
		}
	})
})
const port = 3033
server.listen(port, () => {
	console.log(`Server is listening on http://localhost:${port}`)
})
