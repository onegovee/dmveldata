const fs = require('fs');
const vm = require('vm');

// Step 1: Read the original file
const scriptContent = fs.readFileSync('data/entry_exit.js', 'utf8');

// Step 2: Create a VM context and execute the script
const context = {};
vm.createContext(context);
vm.runInContext(scriptContent, context);

// Step 3: Extract and export a specific variable
const variableName = 'entryExits'; // Specify the variable you are interested in
const filePath = `data/entryExits.json`;
fs.writeFileSync(filePath, JSON.stringify(context[variableName], null, 2), 'utf8');
