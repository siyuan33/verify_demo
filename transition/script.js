document
  .getElementById("loginForm")
  .addEventListener("submit", function (event) {
    event.preventDefault();
    document.getElementById("loginContainer").style.display = "none";
    var directoryItems = document.querySelectorAll(".directory-item");
    var directoryContainer = document.getElementById("directoryContainer");
    directoryContainer.classList.add("active");
    // Reset the transform to prevent further animation
    directoryItems.forEach(function (item) {
      item.style.transform = "translateY(0) scale(1)";
    });
  });
