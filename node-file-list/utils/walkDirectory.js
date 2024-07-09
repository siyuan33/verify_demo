/**
 *  枚举某个路径下的所有文件
 */
const fs = require('fs')
const path = require('path')
function getDictTree(dirPath, excludeDirs = []) {
	const name = path.basename(dirPath)
	const item = { name }
	let stats
	try {
		stats = fs.statSync(dirPath)
	} catch (e) {
		console.error(`读取错误 ${dirPath}: ${e.message}`)
		return null
	}
	if (stats.isDirectory()) {
		if (excludeDirs.includes(name)) {
			return null
		}
		item.type = 'dict'
		item.children = []
		try {
			const items = fs.readdirSync(dirPath)
			items.forEach((child) => {
				const childPath = path.join(dirPath, child)
				const childItem = getDictTree(childPath, excludeDirs)

				if (childItem) {
					item.children.push(childItem)
				}
			})
		} catch (e) {
			console.error(`找不到文件 ${dirPath}: ${e.message}`)
		}
	} else {
		item.type = 'file'
	}
	return item
}

module.exports = {
	getDictTree
}
