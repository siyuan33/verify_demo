/**
 * 同步某个文件下的所有文件到另一个文件
 */
const fs = require('fs')
const path = require('path')

function copyFolderSync(sourceDir, targetDir) {
	// 创建目标文件夹
	fs.mkdirSync(targetDir, { recursive: true })

	// 获取源文件夹中的所有文件和子文件夹
	const files = fs.readdirSync(sourceDir)

	// 遍历源文件夹中的所有文件和子文件夹
	files.forEach((file) => {
		const srcPath = path.join(sourceDir, file)
		const destPath = path.join(targetDir, file)

		// 如果是文件夹，则递归复制文件夹
		if (fs.statSync(srcPath).isDirectory()) {
			copyFolderSync(srcPath, destPath)
		} else {
			// 如果是文件，则复制文件
			fs.copyFileSync(srcPath, destPath)
		}
	})
}

module.exports = { copyFolderSync }

