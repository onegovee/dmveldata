const { PutObjectCommand, HeadObjectCommand, S3Client, S3ServiceException } = require("@aws-sdk/client-s3");
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const https = require('https');
const vm = require('vm');
const crypto = require('crypto');

const s3 = new S3Client({});

// Get environment variables
let bucketName = process.env.BUCKET_NAME
let exportUrl = process.env.EXPORT_URL
let exportVarName = process.env.EXPORT_VAR_NAME
const objectKey = `data/${exportVarName}.json`

exports.handler = async (event, context) => {
  console.log("EVENT: \n" + JSON.stringify(event, null, 2));
  
  // add some jitter
  const randNum = Math.floor(Math.random() * 50) + 1;
  console.log(`Sleeping for ${randNum} seconds...`);
  await sleep(randNum * 1000);
  
  try {
    // download and extract json content
    const downloadContent = await downloadFile(exportUrl);

    // check hash
    const newHash = calculateHash(downloadContent);
    const previousHash = await getPreviousHash();

    if (previousHash !== newHash) {
      console.log("File has changed, uploading...");
      await uploadFile(downloadContent, newHash);
    } else {
      console.log("File is unchanged. Skipping upload.");
    }
  } catch (error) {
    console.error("Error:", error);
  }
};

async function uploadFile(data, hash) {
  // extract json content
  const context = {};
  vm.createContext(context);
  vm.runInContext(data, context);
  const jsonContent = JSON.stringify(data[exportVarName], null, 2);
  
  // upload to s3
  try {
    const command = new PutObjectCommand({
      Bucket: bucketName,
      Key: objectKey,
      Body: jsonContent,
      ContentType: "application/json",
      Metadata: { hash },
    });
    const response = await s3.send(command);
    console.log(response);
  } catch (error) {
    if (error instanceof S3ServiceException) {
      console.error(
        `Error while uploading object - ${error.name}: ${error.message}`,
      );
    } else {
      throw error;
    }
  }
}

async function getPreviousHash() {
  // get metadata for the object from s3
  try {
    const command = new HeadObjectCommand({
        Bucket: bucketName,
        Key: objectKey,
    });
    const response = await s3.send(command);
    return response.Metadata?.hash || null;
  } catch (error) {
    if (error instanceof S3ServiceException) {
      console.error(
        `Error while getting metadata - ${error.name}: ${error.message}`,
      );
    } else {
      throw error;
    }
  }
}

function calculateHash(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

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
