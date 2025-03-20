const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

// Load the shared configuration
const configPath = path.join(__dirname, "config.json");
const config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
const parameterRanges = config.parameterRanges;
const parameters = config.parameters.all; // Add this line

async function resizeImage(inputPath, outputPath) {
  try {
    await sharp(inputPath)
      .resize(307, 63, {
        fit: "cover",
        position: "center",
      })
      .png({ quality: 100, compressionLevel: 0 })
      .toFile(outputPath);
    console.log(`Image resized and saved to ${outputPath}`);
  } catch (error) {
    console.error("Error resizing image:", error);
  }
}

// Create a single browser instance that will be reused
let browserInstance = null;

// Modify the getBrowser function to include more options
async function getBrowser() {
  if (!browserInstance) {
    browserInstance = await puppeteer.launch({
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-first-run",
        "--no-zygote",
        "--single-process",
      ],
      headless: true,
    });
  }
  return browserInstance;
}

// Add a delay function to prevent overwhelming the browser
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Modify the calculateMaxValue function to be more robust
function calculateMaxValue(data, parameter) {
  try {
    const values = data.flatMap((record) => {
      return [
        ...Object.values(record[parameter] || {}).filter(
          (val) => typeof val === "number" && !isNaN(val)
        ),
      ];
    });

    // Handle empty arrays or all NaN values
    if (values.length === 0) {
      console.log(
        `No valid values found for ${parameter}, using default max value`
      );
      const maxRange = Array.isArray(parameterRanges[parameter])
        ? parameterRanges[parameter][2] || 1
        : 1;
      return maxRange;
    }

    let maxValue = Math.max(...values);
    if (!isFinite(maxValue)) {
      console.log(
        `Invalid max value for ${parameter}, using default max value`
      );
      maxValue = 1;
    }

    const maxRange = Array.isArray(parameterRanges[parameter])
      ? parameterRanges[parameter][2] || 0
      : 0;
    return Math.max(1.05 * maxValue, maxRange);
  } catch (error) {
    console.error(`Error calculating max value for ${parameter}:`, error);
    return Array.isArray(parameterRanges[parameter])
      ? parameterRanges[parameter][2] || 1
      : 1;
  }
}

// Modify the processRecords function to handle errors better
async function processRecords() {
  try {
    console.log("Starting to process records...");
    const dataPath = path.join(__dirname, "data.json");
    const rawData = fs.readFileSync(dataPath, "utf-8");
    const records = JSON.parse(rawData);
    console.log(`Loaded ${records.length} records from data.json`);

    for (const record of records) {
      const participantId = record["Participant ID"];
      let sampleDate = record["Sample_date"];

      if (!participantId || !sampleDate) {
        console.log("Skipping record with missing ID or date:", record);
        continue;
      }

      console.log(
        `Processing record for participant ${participantId}, date ${sampleDate}`
      );

      // Split the date string into its components
      const [month, day, year] = sampleDate.split("/");

      // Update the sampleDate directly in the "yyyy-mm-dd" format
      sampleDate = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
      const recordFolder = path.join(
        __dirname,
        "images/output/",
        participantId,
        sampleDate
      );
      fs.mkdirSync(recordFolder, { recursive: true });

      // Process one parameter at a time
      for (const parameter of parameters) {
        try {
          let parameter_type = record[`${parameter}_type`];

          // Skip if no parameter type is defined
          if (parameter_type === undefined) {
            console.log(`Skipping parameter ${parameter} - no type defined`);
            continue;
          }

          console.log(
            `Processing parameter: ${parameter}, type: ${parameter_type}`
          );

          let minRange,
            maxRange,
            maxValue,
            customBarConfig = null;

          // Process based on parameter type
          if (parameter_type === 0) {
            // Custom type 0 with labels
            customBarConfig = parameterRanges[parameter];
            // Last value in the array is the max value
            maxValue =
              parameterRanges[parameter][parameterRanges[parameter].length - 1];
            minRange = 0;
            maxRange = maxValue;
          } else if (parameter_type === 1) {
            maxValue = calculateMaxValue(records, parameter);
            [minRange, maxRange] = parameterRanges[parameter] || [0, 0];
          } else if (parameter_type === 2) {
            if (parameter === "Ammonia") {
              maxValue = 6;
            } else {
              maxValue = 1;
            }
            minRange = 0;
            maxRange = maxValue;
          }

          // Process one item at a time
          for (const item of [
            "Outdoor",
            "Outdoor_Average",
            "FF",
            "FF_Average",
            "AF",
          ]) {
            try {
              // Get value based on parameter type
              let value;
              if (
                parameter_type === 0 &&
                Array.isArray(parameterRanges[parameter]) &&
                typeof parameterRanges[parameter][0] === "string"
              ) {
                // For custom type 0, try to get value from specific field or parameter field
                value = Number(record[`${parameter}_${item}`]);
                if (typeof value !== "number" || isNaN(value)) {
                  value = Number(record[parameter]);
                }
              } else {
                value = Number(record[`${parameter}_${item}`]);
              }

              if (typeof value !== "number" || isNaN(value)) {
                console.log(
                  `Skipping ${parameter}_${item} - invalid value: ${value}`
                );
                continue;
              }

              const outputFilePath = path.join(
                recordFolder,
                `${parameter}_${item}.png`
              );

              // Generate image one at a time
              await generateImage(
                parameter_type,
                value,
                maxValue,
                minRange,
                maxRange,
                outputFilePath,
                customBarConfig
              );

              // Add a small delay between image generations
              await delay(100);
            } catch (itemError) {
              console.error(
                `Error processing ${parameter}_${item}:`,
                itemError
              );
              // Continue with next item
            }
          }
        } catch (paramError) {
          console.error(`Error processing parameter ${parameter}:`, paramError);
          // Continue with next parameter
        }
      }
    }
  } catch (error) {
    console.error("Error processing all records:", error);
  } finally {
    if (browserInstance) {
      console.log("Closing browser...");
      try {
        await browserInstance.close();
      } catch (e) {
        console.error("Error closing browser:", e);
      }
      browserInstance = null;
      console.log("Browser closed successfully");
    }
    console.log("All records processed successfully");
  }
} // End of processRecords

// Add a timeout to the entire process
const TIMEOUT_MINUTES = 15;
const timeout = setTimeout(() => {
  console.error(`Process timed out after ${TIMEOUT_MINUTES} minutes`);
  if (browserInstance) {
    browserInstance.close().catch(console.error);
  }
  process.exit(1);
}, TIMEOUT_MINUTES * 60 * 1000);

// Run the process with the timeout
processRecords()
  .catch((err) => console.error("Error processing records:", err))
  .finally(() => {
    clearTimeout(timeout);
  });

// Fix the HTML template issue - there was a missing opening < in the HTML tag
async function generateImage(
  type,
  value,
  maxValue,
  minRange,
  maxRange,
  outputFilePath,
  customBarConfig = null
) {
  const browser = await getBrowser();
  let page = null;

  try {
    page = await browser.newPage();

    // Set resource timeout to prevent hanging
    await page.setDefaultNavigationTimeout(30000);
    await page.setDefaultTimeout(30000);

    // Prepare custom labels and scales for type 0
    let labelsHTML = "";

    if (type === 0 && customBarConfig) {
      // Extract labels and values
      const pairs = [];
      for (let i = 0; i < customBarConfig.length; i += 2) {
        if (i + 1 < customBarConfig.length) {
          pairs.push({
            label: customBarConfig[i],
            value: customBarConfig[i + 1],
          });
        }
      }

      // Generate HTML for labels
      labelsHTML = '<div class="labels">';
      // Add all labels first
      for (let i = 0; i < pairs.length; i++) {
        if (i === 0) {
          const labelWidth = (pairs[i].value / maxValue) * 313;
          labelsHTML += `<label style="width:${labelWidth}px">${pairs[i].label}</label>`; // Fixed typo: labelwidth -> labelWidth
        } else {
          const labelWidth =
            ((pairs[i].value - pairs[i - 1].value) / maxValue) * 313;
          labelsHTML += `<label style="width:${labelWidth}px">${pairs[i].label}</label>`;
        }

        // Add range divs for all except the last label
        if (i < pairs.length - 1) {
          labelsHTML += `
            <div class="range">
              <line></line>
              <div>${pairs[i].value}</div>
            </div>
          `;
        }
      }

      labelsHTML += "</div>";
    } else {
      // Default labels for water hardness
      labelsHTML = `
    <div class="labels">
      <label>Soft</label>
      <div class="range">
        <line></line>
        <div>60</div>
      </div>

      <label>Moderate</label>
      <div class="range">
        <line></line>
        <div>120</div>
      </div>
      <label>Hard</label>
    </div>`;
    }
    const pageContent = `
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          /* CSS copied from your design */
          html,
          body {
            margin: 0;
            padding: 0;
          }
          body {
            padding: 0 14px;
          }
          #bar {
            position: relative;
            width: 313px;
            height: 6px;
            margin-top: 30px;
            border-radius: 124px;
            background: #F7B32B;
          }

          #dot {
            position: relative;
            display: flex;
            width: 16px;
            height: 16px;
            justify-content: center;
            align-items: center;
            gap: 10px;
            border-radius: 20px;
            background: #252a31;
            position: absolute;
            top: -6px;
            z-index: 9;
          }

          #value {
            position: absolute;
            top: -22px;
            font-family: Arial, sans-serif;
            font-size: 16px;
            color: black;
            text-align: center;
          }

          #dot-inner {
            width: 8px;
            height: 8px;
            border-radius: 8px;
            background-color: #e1ddcc;
          }

          .labels {
            display: flex;
            width: 313px;
          }

          .range-labels {
            position: relative;
            display: flex;
            width: 313px;
          }

          label {
            padding-top: 8px;
            text-align: center;
            color: #a5a5a5;
            font-family: Inter;
            font-size: 14px;
          }
          .range-label{
            position:absolute;
            padding-top: 6px;
            text-align: center;
            color: #a5a5a5;
            font-family: Inter;
            font-size: 12px;
            width: 90px;
            text-align: center;
          }

          line {
            width: 1px;
            height: 14px;
            background: #a5a5a5;
            margin-bottom: 6px;
          }

          .range {
            display: flex;
            flex-direction: column;
            align-items: center;
            color: #a5a5a5;
            font-family: Inter;
            font-size: 14px;
          }
          .range-node {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            color: #a5a5a5;
            font-family: Inter;
            font-size: 14px;
          }
          #normal-range {
            position: absolute;
            width: 200px;
            height: 6px;
            border-radius: 124px;
            background: #ABBF63;
            left: 0px;

          }
          #minRange {
            position: absolute;
            top: 18px;
            text-align: center;
          }
          #maxRange {
            position: absolute;
            top: 18px;
            text-align: center;
          }
          
        </style>
      </head>
      <body>
        <div id="bar">
          <div id="normal-range">

          </div>
          <div id="dot">
            <div id="dot-inner"></div>
            <div id="value">${value}</div>
          </div>
        </div>
        ${labelsHTML}
        <div class="range-labels">
          <div class="range-node">
            <line></line>
            <div id="minRange">0.2</div>
          </div>
          <div class="range-label">Acceptable Range</div>

          <div class="range-node">
            <line></line>
            <div id="maxRange">4</div>
          </div>
        </div>
        </div>

        <script>
          // JavaScript to update the position of the dot
          const bar = document.getElementById("bar");
          const dot = document.getElementById("dot");
          const minRangeNode=document.getElementsByClassName("range-node")[0];
          const maxRangeNode=document.getElementsByClassName("range-node")[1];
          const rangeLabel=document.getElementsByClassName("range-label")[0];
          const normalRange=document.getElementById("normal-range");

          function updateBar(type, value, maxValue, minRange, maxRange, customConfig) {
            // type: 0 without unregulated range, 1 with regulated range, 2 without range
            if (value < 0 || value > maxValue) {
              console.error("Invalid value.");
              return;
            }
            
            if (type==0){
              document.getElementsByClassName("range-labels")[0].style.display="none";
              bar.style.background="linear-gradient(90deg, #e1ddcc 0%, #b1aea1 100%)";
              normalRange.style.display="none";
              
              // For type 0, position the labels correctly if using custom config
              if (customConfig) {
                const maxVal = customConfig[customConfig.length - 1];
                const labelsContainer = document.querySelector('.labels');
                
                // Make sure labels are positioned correctly
                if (labelsContainer && labelsContainer.children.length > 0) {
                  for (let i = 0; i < labelsContainer.children.length; i++) {
                    const labelDiv = labelsContainer.children[i];
                    // Position adjustments can be made here if needed
                  }
                }
              }
            }
            if (type==1){
              document.getElementsByClassName("labels")[0].style.display="none";
            }
            if (type==2){
              document.getElementsByClassName("range-labels")[0].style.display="none";
              bar.style.background="linear-gradient(90deg, #e1ddcc 0%, #b1aea1 100%)";
              normalRange.style.display="none";
              document.getElementsByClassName("labels")[0].style.display="none";
            }

            const barWidth = bar.offsetWidth;
            let minRangeDistance=minRange*313/maxValue
            let maxRangeDistance=(maxRange*313/maxValue)-minRangeDistance

            minRangeNode.style.left =minRangeDistance+"px"
            maxRangeNode.style.left =maxRangeDistance+minRangeDistance-2+"px"
            rangeLabel.style.left =(maxRangeDistance/2+minRangeDistance-45)+"px"
            normalRange.style.left=minRangeDistance+"px";
            normalRange.style.width=maxRangeDistance+"px";

            // Position the dot based on the value
            const dotPosition = (value / maxValue) * barWidth;
            dot.style.left = (dotPosition - 8) + "px";
          }

          // Set the value dynamically
          updateBar(${type}, ${value}, ${maxValue}, ${minRange}, ${maxRange}, ${JSON.stringify(
      customBarConfig || null
    )});
        </script>
      </body>
    </html>
    `;

    await page.setContent(pageContent);

    await page.setViewport({ width: 341, height: 70, deviceScaleFactor: 0.9 });
    await page.waitForSelector("#bar", { timeout: 5000 });

    // Log the final rendered HTML for #bar only for type 0 parameters
    if (type === 0) {
      // Create debug folder if it doesn't exist
      const debugFolder = path.join(__dirname, "debug");
      if (!fs.existsSync(debugFolder)) {
        fs.mkdirSync(debugFolder);
      }

      // Save the complete page content to an HTML file
      const debugFilePath = path.join(
        debugFolder,
        `page_${path.basename(outputFilePath, ".png")}.html`
      );
      fs.writeFileSync(debugFilePath, pageContent);
      console.log(`Complete HTML template saved to: ${debugFilePath}`);
    }

    await page.screenshot({ path: outputFilePath });
    console.log(`Image generated at ${outputFilePath}`);
    return outputFilePath;
  } catch (error) {
    console.error(`Error generating image for ${outputFilePath}:`, error);
    // Continue processing despite errors
  } finally {
    if (page) {
      try {
        await page.close();
      } catch (e) {
        console.error("Error closing page:", e);
      }
    }
  }
}
