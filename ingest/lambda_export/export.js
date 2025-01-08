const { S3Client, HeadObjectCommand, } = require("@aws-sdk/client-s3");
const { Upload } = require("@aws-sdk/lib-storage");
const https = require("https");
const crypto = require("crypto");
const vm = require("vm");

const s3 = new S3Client({});
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Environment variables
const bucketName = process.env.BUCKET_NAME;
const exportUrl = process.env.EXPORT_URL;
const exportVarName = process.env.EXPORT_VAR_NAME;
const objectKey = `data/${exportVarName}.json`;

exports.handler = async (event) => {
  console.log("EVENT:", JSON.stringify(event, null, 2));

  // Add jitter
  const jitter = Math.floor(Math.random() * 50) + 1;
  console.log(`Sleeping for ${jitter} seconds...`);
  await sleep(jitter * 1000);

  try {
    console.log("Downloading file...");
    const fileContent = await downloadFile(exportUrl);

    console.log("Extracting variable...");
    const extractedData = extractVariable(fileContent, exportVarName);

    console.log("Calculating hash...");
    const newHash = calculateHash(extractedData);

    console.log("Checking previous hash...");
    const previousHash = await getPreviousHash();

    if (newHash !== previousHash) {
      console.log("File has changed. Uploading...");
      await uploadFile(extractedData, newHash);
    } else {
      console.log("File is unchanged. Skipping upload.");
    }
  } catch (error) {
    console.error("Error in Lambda execution:", error.message);
  }
};

async function uploadFile(content, hash) {
  try {
    const upload = new Upload({
      client: s3,
      params: {
        Bucket: bucketName,
        Key: objectKey,
        Body: JSON.stringify(content, null, 2),
        ContentType: "application/json",
        Metadata: { hash },
      },
    });

    upload.on("httpUploadProgress", (progress) =>
      console.log(`Uploaded ${progress.loaded} bytes`)
    );

    await upload.done();
    console.log("Upload completed successfully.");
  } catch (error) {
    console.error("Error uploading file to S3:", error.message);
    throw error;
  }
}

async function getPreviousHash() {
  try {
    const command = new HeadObjectCommand({
      Bucket: bucketName,
      Key: objectKey,
    });

    const response = await s3.send(command);
    return response.Metadata?.hash || null;
  } catch (error) {
    if (error.name === "NotFound") {
      console.log("No previous object found. Returning null hash.");
      return null;
    }
    console.error("Error fetching object metadata:", error.message);
    throw error;
  }
}

function calculateHash(data) {
  return crypto.createHash("sha256").update(JSON.stringify(data)).digest("hex");
}

function downloadFile(url) {
  return new Promise((resolve, reject) => {
    let data = "";
    https
      .get(url, (response) => {
        if (response.statusCode !== 200) {
          reject(new Error(`Failed to fetch file. HTTP status: ${response.statusCode}`));
          return;
        }
        response.on("data", (chunk) => (data += chunk));
        response.on("end", () => resolve(data));
      })
      .on("error", (err) => reject(new Error(`Error during download: ${err.message}`)));
  });
}

function extractVariable(content, variableName) {
  try {
    const sandbox = {};
    vm.createContext(sandbox); // Create a secure sandbox
    vm.runInContext(content, sandbox); // Execute the content safely
    if (!sandbox.hasOwnProperty(variableName)) {
      throw new Error(`Variable "${variableName}" not found in the script.`);
    }
    return sandbox[variableName]; // Extract the variable
  } catch (error) {
    console.error("Error during variable extraction:", error.message);
    throw error;
  }
}