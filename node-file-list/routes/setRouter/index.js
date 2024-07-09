const fs = require('fs')
const path = require('path')

function getJsFilesInDir(dir) {
	const dirPath = path.resolve(__dirname, dir)
	let jsFiles = []

	if (fs.existsSync(dirPath)) {
		const files = fs.readdirSync(dirPath)

		jsFiles = files
			.filter((file) => path.extname(file) === '.js')
			.map((file) => path.basename(file, '.js'))
	} else {
		console.log(`${dirPath} 不存在`)
	}

	return jsFiles
}

// 获取 @/routes 目录下的所有 JavaScript 文件
const jsFiles = getJsFilesInDir('../')

// 注册所有路由
function setRouter(app) {
	for (const iterator of jsFiles) {
		app.use('/' + iterator, require('@/routes/' + iterator))
	}
}
module.exports = { setRouter }
