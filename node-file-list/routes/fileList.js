var express = require('express')
const path = require('path')

var router = express.Router()
const { getDictTree } = require('../utils/walkDirectory.js')
router.get('/', function (req, res, next) {
	// 遍历的文件目录
	const dirPath = path.resolve('./models')
	// 要排除的目录列表
	const excludeDirs = ['excludeDir']
	const directoryTree = getDictTree(dirPath, excludeDirs)
	res.send({
		...directoryTree
	})
})

module.exports = router
