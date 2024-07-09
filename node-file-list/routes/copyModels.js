var express = require('express')
var router = express.Router()
const { copyFolderSync } = require('../utils/copyFolderSync')
const cron = require('node-cron')

/* GET home page. */
router.get('/', function (req, res, next) {
	console.log('CopyWating...')
	const sourceDir = './models'
	const targetDir = './models_target'

	cron.schedule('59 23 * * *', () => {
		copyFolderSync(sourceDir, targetDir)
		console.log('Copy task completed')
	})

	res.send('copyModels')
})

module.exports = router
