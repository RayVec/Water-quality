const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const parameterRanges = {
  Disinfectant: [0.2, 4, 6],
  // Monochloramine: [0.2, 4, 6],
  // Chlorine: [0.2, 4, 6],
  Lead: [0, 15, 30],
  Nitrate: [0, 10, 15],
  Nitrite: [0, 1, 1.5],
  Turbidity: [0, 1, 1.5],
  pH: [6.5, 9.5, 10],
  Ammonia: "No",
};

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

async function generateImage(
  type,
  value,
  maxValue,
  minRange,
  maxRange,
  outputFilePath
) {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  await page.setContent(`
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
        justify-content: space-between;
        width: 313px;
      }

      .range-labels {
        position: relative;
        display: flex;
        width: 313px;
      }

      label {
        padding-top: 8px;
        flex: 1;
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
        <div id="value">0</div>
      </div>
    </div>
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
    </div>
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


      const maxHardness = 180;

      function updateBar(type,value, maxValue, minRange, maxRange) {
        // type: 0 without unregulated range, 1 with regulated range, 2 without range
        if (value < 0 || value > maxValue) {
          console.error("Invalid value.");
          return;
        }
        if (type==0){
          document.getElementsByClassName("range-labels")[0].style.display="none";
          bar.style.background="linear-gradient(90deg, #e1ddcc 0%, #b1aea1 100%)";
          normalRange.style.display="none";

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


        dot.style.left = (value*313/maxValue - 8)+"px";
        document.getElementById("value").textContent = value;
        document.getElementById("minRange").textContent = minRange;
        document.getElementById("maxRange").textContent = maxRange;
      }

      // Set the water hardness value dynamically
      updateBar(${type},${value},${maxValue},${minRange},${maxRange});
    </script>
  </body>
</html>
  `);

  await page.setViewport({ width: 341, height: 70, deviceScaleFactor: 0.9 });
  await page.waitForSelector("#bar");
  await page.screenshot({ path: outputFilePath });
  console.log(`Image generated at ${outputFilePath}`);
  await browser.close();
}

function calculateMaxValue(data, parameter) {
  const values = data.flatMap((record) => {
    return [
      ...Object.values(record[parameter] || {}).filter(
        (val) => typeof val === "number"
      ),
    ];
  });
  let maxValue = Math.max(...values);
  const maxRange = parameterRanges[parameter][2] || 0;
  return Math.max(1.05 * maxValue, maxRange);
}

async function processRecords() {
  const dataPath = path.join(__dirname, "data.json");
  const rawData = fs.readFileSync(dataPath, "utf-8");
  const records = JSON.parse(rawData);

  for (const record of records) {
    console.log(record);
    const participantId = record["Participant ID"];
    let sampleDate = record["Sample_date"];

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

    for (const parameter of Object.keys(parameterRanges)) {
      if (!record[`${parameter}_type`]) continue;
      console.log(parameter);
      let parameter_type = record[`${parameter}_type`];
      let minRange, maxRange, maxValue;
      maxValue = calculateMaxValue(records, parameter);
      console.log("maxValue", maxValue);
      if (parameter_type == 1) {
        [minRange, maxRange] = parameterRanges[parameter] || [0, 0];
      }
      if (parameter_type == 2) {
        if (parameter === "Ammonia") {
          maxValue = 6;
          minRange = 0;
          maxRange = 0;
        } else {
          maxValue = 1;
          minRange = 0;
          maxRange = maxValue;
        }
      }
      console.log(minRange, maxRange);

      for (const item of [
        "Outdoor",
        "Outdoor_Average",
        "FF",
        "FF_Average",
        "AF",
      ]) {
        const value = Number(record[`${parameter}_${item}`]);
        console.log(value);
        if (typeof value !== "number") continue;

        const outputFilePath = path.join(
          recordFolder,
          `${parameter}_${item}.png`
        );
        await generateImage(
          record[`${parameter}_type`],
          value,
          maxValue,
          minRange,
          maxRange,
          outputFilePath
        );
      }
    }
  }
}

processRecords().catch((err) =>
  console.error("Error processing records:", err)
);
