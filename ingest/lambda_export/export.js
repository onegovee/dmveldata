const { PutObjectCommand, S3Client, S3ServiceException } = require("@aws-sdk/client-s3");
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const https = require('https');
const vm = require('vm');

// Get environment variables
let bucketName = process.env.BUCKET_NAME
let exportUrl = process.env.EXPORT_URL
let exportVarName = process.env.EXPORT_VAR_NAME

exports.handler = async (event, context) => {
  console.log("EVENT: \n" + JSON.stringify(event, null, 2));
  
  // add some jitter
  const randNum = Math.floor(Math.random() * 50) + 1;
  console.log(`Sleeping for ${randNum} seconds...`);
  await sleep(randNum * 1000);
  
  try {
    // download and extract json content
    const downloadContent = await downloadFile(exportUrl);

    const context = {};
    vm.createContext(context);
    vm.runInContext(downloadContent, context);

    const jsonContent = JSON.stringify(context[exportVarName], null, 2);

    // upload content to s3
    const client = new S3Client({});
    const command = new PutObjectCommand({
      Bucket: bucketName,
      Key: `data/${exportVarName}.json`,
      Body: jsonContent,
      ContentType: 'application/json',
    });

    const response = await client.send(command);
    console.log(response);

  } catch (caught) {
    if (caught instanceof S3ServiceException) {
      console.error(
        `Error from S3 while uploading object to ${bucketName}. ${caught.name}: ${caught.message}`,
      );
    } else {
      throw caught;
    }
  }
};

function downloadFile(url) {
  return new Promise((resolve, reject) => {
    let data = '';
    https.get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to get file: ${response.statusCode}`));
        return;
      }
      response.on('data', (chunk) => (data += chunk));
      response.on('end', () => resolve(data));
    }).on('error', (err) => reject(err));
  });
}
