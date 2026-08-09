const puppeteer = require("puppeteer");
const fs = require("fs");

(async () => {
  // Launch Puppeteer
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  // Define HTML and CSS
  const htmlContent = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Example</title>
      <style>
        body {
          display: flex;
          justify-content: center;
          align-items: center;
          height: 100vh;
          margin: 0;
          background-color: #f0f0f0;
        }
        .card {
          width: 300px;
          height: 200px;
          background: linear-gradient(45deg, #ff6b6b, #f8e71c);
          display: flex;
          justify-content: center;
          align-items: center;
          border-radius: 10px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          font-family: Arial, sans-serif;
          color: white;
          font-size: 50px;
          text-align: center;
        }
      </style>
    </head>
    <body>
      <div class="card">
        heloo jenny!
      </div>
    </body>
    </html>
  `;

  // Set content for the page
  await page.setContent(htmlContent);

  // Define the output file path
  const outputPath = "example.png";

  // Capture a screenshot
  await page.screenshot({ path: outputPath, fullPage: true });

  console.log(`Screenshot saved to ${outputPath}`);

  // Close the browser
  await browser.close();
})();
