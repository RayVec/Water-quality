const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");

// Function to generate the water hardness bar image
async function generateImage(waterHardnessValue) {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  // Set the content of the page to your HTML and CSS
  await page.setContent(`
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          /* CSS copied from your design */
          html, body {
          margin: 0;
          padding: 0;
        }
          body {
          padding: 0 14px}
          #water-hardness-bar {
            position: relative;
            width: 313px;
            height: 6px;
            margin-top: 30px;
            border-radius: 124px;
            background: linear-gradient(90deg, #e1ddcc 0%, #b1aea1 100%);
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
          }

          #value {
            position: absolute;
            top: -22px;
            font-family: Arial, sans-serif;
            font-size: 16px;
            color: black;
            text-size:center;
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

          label {
            padding-top: 8px;
            flex: 1;
            text-align: center;
            color: #a5a5a5;
            font-family: Inter;
            font-size: 14px;
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
        </style>
      </head>
      <body>
        <div id="water-hardness-bar">
          <div id="dot">
            <div id="dot-inner"></div>
            <div id="value">${waterHardnessValue}</div>
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

        <script>
          // JavaScript to update the position of the dot
          const waterHardnessBar = document.getElementById("water-hardness-bar");
          const dot = document.getElementById("dot");

          const maxHardness = 180;

          function updateBar(waterHardness) {
            if (waterHardness < 0 || waterHardness > maxHardness) {
              console.error("Invalid water hardness value.");
              return;
            }

            const barWidth = waterHardnessBar.offsetWidth;
            const dotPosition = (waterHardness / maxHardness) * barWidth - 8;
            dot.style.left = \`\${dotPosition}px\`;
          }

          // Set the water hardness value dynamically
          updateBar(${waterHardnessValue});
        </script>
      </body>
    </html>
  `);

  // Set the viewport to match the content size
  await page.setViewport({ width: 341, height: 70 });

  // Wait for the bar to render and position the dot
  await page.waitForSelector("#water-hardness-bar");

  // Take a screenshot of the rendered bar
  const outputFilePath = path.join(
    __dirname,
    `./images/water-hardness-${waterHardnessValue}.png`
  );
  await page.screenshot({ path: outputFilePath });

  console.log(`Image generated at ${outputFilePath}`);

  await browser.close();
}

// Example usage: generate image with water hardness value 150
generateImage(0);
