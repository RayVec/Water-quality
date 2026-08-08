const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");
const XLSX = require("xlsx"); // Import the xlsx library

// --- Shared configuration ---
// Loaded first so everything below can read its constants from config.json
// instead of hardcoding them here as well as in the Python scripts.
const configPath = path.join(__dirname, "config.json");
const config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
const parameterRanges = config.parameterRanges;
const parameters = config.parameters.all;
const barMaxValues = config.barDefaults.maxValue;

// --- Translation Setup ---
const TRANSLATIONS_FILE = path.join(
  __dirname,
  "data",
  "reference",
  config.files.translations
);
const ENGLISH_COL = config.files.translationColumns.english;
const SPANISH_COL = config.files.translationColumns.spanish;
let translations = {}; // Global object to hold loaded translations

function loadTranslations() {
  const translationsLookup = {};
  if (!fs.existsSync(TRANSLATIONS_FILE)) {
    console.warn(
      `Translations file not found: ${TRANSLATIONS_FILE}. Using English text only.`
    );
    return translationsLookup; // Return empty if file doesn't exist
  }

  try {
    console.log(`Loading translations from ${TRANSLATIONS_FILE}...`);
    const workbook = XLSX.readFile(TRANSLATIONS_FILE);
    const sheetName = workbook.SheetNames[0]; // Assume translations are on the first sheet
    const worksheet = workbook.Sheets[sheetName];
    const jsonData = XLSX.utils.sheet_to_json(worksheet);

    for (const row of jsonData) {
      const englishText = row[ENGLISH_COL]
        ? String(row[ENGLISH_COL]).trim()
        : null;
      const spanishText = row[SPANISH_COL]
        ? String(row[SPANISH_COL]).trim()
        : null;

      if (englishText && spanishText) {
        // Only add if both exist and Spanish is not empty
        translationsLookup[englishText] = spanishText;
      }
    }
    console.log(
      `Successfully loaded ${
        Object.keys(translationsLookup).length
      } translations.`
    );
    return translationsLookup;
  } catch (error) {
    console.error(
      `Error loading or processing translations from ${TRANSLATIONS_FILE}:`,
      error
    );
    return {}; // Return empty on error
  }
}

// Load translations when the script starts
translations = loadTranslations();

// Helper function to get translation or default to English
function translate(englishText) {
  return translations[englishText] || englishText;
}
// --- End Translation Setup ---



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
// Read the run manifest named by $MANIFEST. Same file the Python stages read,
// so the batch and its paths are defined in exactly one place. No fallback:
// guessing a default here is how a stage ends up writing over another batch.
function loadManifest() {
  const manifestPath = process.env.MANIFEST;
  if (!manifestPath) {
    console.error("\n❌ MANIFEST is not set.");
    console.error("   Run the pipeline through run_pipeline.py, or point it at a batch:");
    console.error("       MANIFEST='build/<batch>/manifest.json' node bar-gen.js\n");
    process.exit(1);
  }
  if (!fs.existsSync(manifestPath)) {
    console.error(`\n❌ Manifest not found: ${manifestPath}\n`);
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
}

// Fail fast if the browser is unavailable.
//
// Every image is generated inside its own try/catch so that one bad parameter
// cannot abort the batch. That also means a missing browser used to produce 500
// caught errors and still exit 0, so run_pipeline.py reported success while
// writing zero images and the PDFs came out with no scale bars. Check once up
// front instead and stop the pipeline with a real exit code.
async function assertBrowserAvailable() {
  try {
    await getBrowser();
  } catch (error) {
    console.error("\n❌ Could not launch Chrome, so no scale bars can be generated.");
    console.error(`   ${error.message.split("\n")[0]}`);
    console.error("\n   Puppeteer downloads its own Chrome into ~/.cache/puppeteer during");
    console.error("   `npm install`. If that cache was cleared, restore it with:\n");
    console.error("       npx puppeteer browsers install chrome\n");
    process.exit(1);
  }
}

async function processRecords() {
  try {
    // Manifest first: it is the cheap check, and there is no point launching a
    // browser for a run we cannot locate.
    const manifest = loadManifest();
    await assertBrowserAvailable();

    console.log("Starting to process records...");
    const dataPath = path.resolve(manifest.records);
    const rawData = fs.readFileSync(dataPath, "utf-8");
    const records = JSON.parse(rawData);
    console.log(`Batch "${manifest.batch}": loaded ${records.length} records from ${dataPath}`);

    for (const record of records) {
      const participantId = record["Participant_ID"];
      let sampleDate = record["Sample_date"];
      // --- Get Language Preference ---
      const language = record["Language"] || "English"; // Default to English if missing
      const isSpanish = language.toLowerCase() === "spanish";
      // --- End Get Language Preference ---

      if (!participantId || !sampleDate) {
        console.log(
          "Skipping record with missing ID or date:",
          record.Participant_ID
        );
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
        path.resolve(manifest.bars),
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
            // Unregulated parameters have no range, so the bar just needs a
            // sensible upper bound. Per-parameter overrides live in config.json.
            maxValue =
              barMaxValues[parameter] !== undefined
                ? barMaxValues[parameter]
                : barMaxValues._default;
            minRange = 0;
            maxRange = maxValue;
          }

          // Special handling for Disinfectant ranges based on source
          if (parameter === "Disinfectant" && parameter_type === 1) {
            // Check type is 1
            const source = record["Disinfectant_Source"];
            let specificRanges;
            if (source === "Chloramine") {
              specificRanges = parameterRanges["Chloramine"];
            } else if (source === "Chlorine") {
              specificRanges = parameterRanges["Chlorine"];
            }

            if (specificRanges && specificRanges.length >= 2) {
              minRange = specificRanges[0];
              maxRange = specificRanges[1];
              // Ensure maxValue is at least the configured max (3rd element)
              if (specificRanges.length >= 3 && specificRanges[2] > maxValue) {
                maxValue = specificRanges[2];
              }
            } else {
              // Optional: Log warning if source is unknown or ranges are missing
              console.warn(
                `Disinfectant source '${source}' not found in config or invalid range definition for participant ${participantId}. Using default ranges.`
              );
              // Keep the default [minRange, maxRange] assigned earlier for "Disinfectant"
            }
          }

          // Process one item at a time
          const filteredAvailable = record[`${parameter}_Filtered_Available`];
          for (const item of [
            "Outdoor",
            "Outdoor_Average",
            "FF",
            "FF_Average",
            "Filtered",
            "Filtered_Average",
          ]) {
            try {
              // Get value based on parameter type
              const rawValue = record[`${parameter}_${item}`];

              if (
                rawValue === undefined ||
                rawValue === null ||
                (typeof rawValue === "string" && rawValue.trim() === "")
              ) {
                continue;
              }

              if (item.startsWith("Filtered") && filteredAvailable === false) {
                continue;
              }

              let value;
              if (
                parameter_type === 0 &&
                Array.isArray(parameterRanges[parameter]) &&
                typeof parameterRanges[parameter][0] === "string"
              ) {
                // For custom type 0, try to get value from specific field or parameter field
                value = Number(rawValue);
                if (typeof value !== "number" || isNaN(value)) {
                  value = Number(record[parameter]);
                }
              } else {
                value = Number(rawValue);
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

              // Generate image one at a time, passing the language preference
              await generateImage(
                parameter_type,
                value,
                maxValue,
                minRange,
                maxRange,
                outputFilePath,
                customBarConfig,
                participantId,
                isSpanish
              );
              console.log(
                participantId,
                parameter,
                value,
                maxValue,
                minRange,
                maxRange,
                parameter_type
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

// Modify generateImage to accept and use language preference
async function generateImage(
  type,
  value,
  maxValue,
  minRange,
  maxRange,
  outputFilePath,
  customBarConfig = null,
  participantId = "unknown",
  isSpanish = false // Add language flag parameter
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
          const englishLabel = customBarConfig[i];
          pairs.push({
            // Apply translation conditionally
            label: isSpanish ? translate(englishLabel) : englishLabel,
            value: customBarConfig[i + 1],
          });
        }
      }

      // Generate HTML for labels
      labelsHTML = '<div class="labels">';
      // Add all labels first
      for (let i = 0; i < pairs.length; i++) {
        if (i === 0) {
          const labelWidth = (pairs[i].value / maxValue) * 313 - 12;
          labelsHTML += `<label style="width:${labelWidth}px">${pairs[i].label}</label>`;
        }
        // if it's the last label
        else if (i === pairs.length - 1) {
          const labelWidth =
            ((pairs[i].value - pairs[i - 1].value) / maxValue) * 313 - 12;
          labelsHTML += `<label style="width:${labelWidth}px">${pairs[i].label}</label>`;
        } else {
          // 24 is the width of the range div
          const labelWidth =
            ((pairs[i].value - pairs[i - 1].value) / maxValue) * 313 - 24;
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
    } else if (type !== 0 && type !== 1 && type !== 2) {
      // Default labels case (e.g., hardness)
      // Default labels for water hardness - Apply translation conditionally
      const softLabel = isSpanish ? translate("Soft") : "Soft";
      const moderateLabel = isSpanish ? translate("Moderate") : "Moderate";
      const hardLabel = isSpanish ? translate("Hard") : "Hard";
      labelsHTML = `
    <div class="labels">
      <label>${softLabel}</label>
      <div class="range">
        <line></line>
        <div>60</div>
      </div>

      <label>${moderateLabel}</label>
      <div class="range">
        <line></line>
        <div>120</div>
      </div>
      <label>${hardLabel}</label>
    </div>`;
    } else {
      // No labels needed for type 1 or 2
      labelsHTML = '<div class="labels"></div>';
    }

    // Apply translation conditionally to "Acceptable Range"
    const acceptableRangeLabel = isSpanish
      ? translate("Acceptable Range")
      : "Acceptable Range";

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
            overflow: hidden;
            max-width: 341px;
            position: relative;
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
            width: 24px;
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
            <div id="minRange">${minRange}</div>
          </div>
          <div class="range-label">${acceptableRangeLabel}</div> 
          <div class="range-node">
            <line></line>
            <div id="maxRange">${maxRange}</div>
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

    await page.setViewport({ width: 340, height: 70, deviceScaleFactor: 0.9 });
    await page.waitForSelector("#bar", { timeout: 5000 });

    // Save debug HTML for specific parameter types (currently 0 and 1).
    // Off by default: this writes one HTML file per generated bar, which used to
    // pile up ~900 files in debug/. Enable with DEBUG=1 when investigating a bar.
    if (process.env.DEBUG && (type === 0 || type === 1)) {
      // Create debug folder if it doesn't exist
      const debugFolder = path.join(__dirname, "debug");
      if (!fs.existsSync(debugFolder)) {
        fs.mkdirSync(debugFolder);
      }

      // Save the complete page content to an HTML file
      const debugFilePath = path.join(
        debugFolder,
        `${participantId}_${path.basename(outputFilePath, ".png")}.html`
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

// Run the process
processRecords().catch((err) =>
  console.error("Error processing records:", err)
);
