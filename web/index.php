<?php
function valueForConfigKey($key, $rawConfigContent) {
	$start = strpos($rawConfigContent, $key);
	$temp = substr($rawConfigContent, $start);
	$end = strpos($temp, "\n");
	$start = strlen($key);
	$end = $end - $start;
	return trim(substr($temp, $start, $end));
}

$rawConfigContent = file_get_contents('../config/default.ini');
$versionNumber = valueForConfigKey('version:', $rawConfigContent);
$buildName = valueForConfigKey('build_name:', $rawConfigContent);
$buildNumber = valueForConfigKey('build_number:', $rawConfigContent);
?><!DOCTYPE html>
<html lang="en">
<head>
  <title>Scratch to Catrobat Converter</title>
  <meta charset="utf-8">
  <meta name="robots" content="noindex,nofollow"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="http://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
  <link rel="shortcut icon" href="./images/logo/favicon.png" />
  <link rel="stylesheet" href="./css/main.css" media="screen"/>
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.4/jquery.min.js"></script>
  <script type="text/javascript" src="./js/qrcode.min.js"></script>
  <script src="http://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>
  <script type="text/javascript" src="./js/spin.min.js"></script>
  <script>
    // var opts = {
    //   lines: 13, // The number of lines to draw
    //   length: 28, // The length of each line
    //   width: 14, // The line thickness
    //   radius: 42, // The radius of the inner circle
    //   scale: 1, // Scales overall size of the spinner
    //   corners: 1, // Corner roundness (0..1)
    //   color: '#000', // #rgb or #rrggbb or array of colors
    //   opacity: 0.25, // Opacity of the lines
    //   rotate: 0, // The rotation offset
    //   direction: 1, // 1: clockwise, -1: counterclockwise
    //   speed: 1, // Rounds per second
    //   trail: 60, // Afterglow percentage
    //   fps: 20, // Frames per second when using setTimeout() as a fallback for CSS
    //   zIndex: 2e9, // The z-index (defaults to 2000000000)
    //   className: 'spinner', // The CSS class to assign to the spinner
    //   top: '50%', // Top position relative to parent
    //   left: '50%', // Left position relative to parent
    //   shadow: false, // Whether to render a shadow
    //   hwaccel: false, // Whether to use hardware acceleration
    //   position: 'absolute' // Element positioning
    // };
    // var target = document.getElementById('foo');
    // var spinner = new Spinner(opts).spin(target);

    function getProjectIDFromURL(projectURL) {
        if (projectURL == null) {
          return null;
        }
        if (projectURL.indexOf("http://scratch.mit.edu/projects/") == -1 && projectURL.indexOf("https://scratch.mit.edu/projects/") == -1) {
          return null;
        }
        var urlParts = projectURL.split("/");
        if (urlParts.length < 5) {
          return null;
        }
        var projectID = urlParts[urlParts.length - 1];
        if (projectID == "") {
          projectID = urlParts[urlParts.length - 2];
        }
        return projectID;
    }
    function enableSubmitButton() {
      $("#btn-convert").removeClass("deactivate-button").removeClass("activate-button").addClass("activate-button");
    }
    function disableSubmitButton() {
      $("#btn-convert").removeClass("deactivate-button").removeClass("activate-button").addClass("deactivate-button");
    }
    function showErrorMessage(msg) {
      $("#field-url").css("border-color", "#FF0000");
      $("#field-url-validation-result").append($("<div></div>").text(msg).css("color", "#FF0000").css("font-weight", "bold"));
    }
    function showSuccessMessage(msg) {
      $("#field-url").css("border-color", "#006400");
      $("#field-url-validation-result").append($("<div></div>").html(msg).css("color", "#006400").css("font-weight", "bold"));
    }
    function updateAndShowProjectDetails(projectID) {
      $("#field-url-validation-result").html("");
      if (projectID == null) {
        showErrorMessage("Invalid URL given!");
        disableSubmitButton();
        $(this).focus();
        return;
      }
      var projectMetadataURL = "https://scratch.mit.edu/api/v1/project/" + projectID + "/?format=json";
      $.getJSON(projectMetadataURL, function(data) {
        var div = $("<div></div>").html("<b>Project:</b> " + data["title"]);
        var projectMetadataDiv = $("<div></div>").append(div);
        showSuccessMessage(projectMetadataDiv);
      }).error(function(event, jqxhr, exception) {
        showErrorMessage("Invalid project?? No metadata available!");
        disableSubmitButton();
        $(this).focus();
      });
      enableSubmitButton();
    }
    function init() {
    }

    jQuery(document).ready(function($) {
  		$("#btn-convert").removeClass("deactivate-button").addClass("activate-button");
      init();
  		$("#version-link").click(function() {
  			alert("Build: <?php echo $buildName; ?>, <?php echo $buildNumber; ?>");
  			return false;
  		});
  		$("#field-url").on("blur", function () {
        updateAndShowProjectDetails(getProjectIDFromURL($(this).val()));
      }).on("keydown", function(e) {
        if (e.keyCode == 13) {
          updateAndShowProjectDetails(getProjectIDFromURL($(this).val()));
        }
  		});
  		$("#converter_form").submit(function(event) {
        var projectConversionURL = "/api/v1/start_conversion.php?id={0}";
        var projectID = getProjectIDFromURL($("#field-url").val());
        $("#field-url-validation-result").html("");
        if (projectID == null) {
          showErrorMessage("Invalid URL given!");
          disableSubmitButton();
          $(this).focus();
          event.preventDefault();
          return false;
        }
        $.getJSON(projectConversionURL.replace("{0}", projectID), function(data) {

        });
        event.preventDefault();
        return false;
      });
      $("#select_form").submit(function(event) {
        event.preventDefault();
        return false;
      });
      $("#btn-show-url-input").click(function() {
        updateAndShowProjectDetails(getProjectIDFromURL($("#field-url").val()));
        $("#web-convert-modal").modal();
        $("#field-url").focus();
        $("#qrcode").children().remove();
        var qrcode = new QRCode(document.getElementById("qrcode"), {
          width : 200,
          height : 200
        });
        qrcode.makeCode($("#field-url").val());
      });
      $("#btn-show-upload-input").click(function() {
        $("#upload-convert-modal").modal();
      });
    });
  </script>
  <style type="text/css">
  .modal-header {
    background-color: #EEE;
    color: #000;
  }
  .modal-header h4 {
    font-weight: bold;
  }
  .modal-body, .modal-body h2 {
    color: #666;
  }
  .close {
    font-size: 50px;
  }
  </style>
</head>
<body>
  <div class="ribbon">
    <a href="#" id="version-link">version <?php echo $versionNumber; ?></a>
  </div>
  <div id="wrapper">
    <header>
      <nav>
        <div id="header-top">
          <div><a href="https://share.catrob.at/pocketcode/help">Tutorials</a></div>
          <div><a href="http://www.catrobat.org">About</a></div>
        </div>
        <div id="header-left">
          <div id="logo">
            <a href="/pocketcode/">
              <img src="/images/logo/logo_text.png" alt="Pocket Code Logo" />
            </a>
          </div>
        </div>
      </nav>
    </header>

    <article>
      <div id="select-page" style="text-align:center;">
        <p>&nbsp;</p>
        <h2>Convert Scratch projects to Catrobat</h2>
        <p>Quickly turn your Scratch desktop projects into full-fledged mobile Catrobat projects</p>
        <p>&nbsp;</p>
        <div>
          <form id="select_form" action="#">
            <div><input type="submit" name="btn-show-url-input" id="btn-show-url-input" value="Enter URL" class="convert-button activate-button" /></div>
            <div style="margin:20px;margin-bottom:0;font-size:25px;font-weight:bold;">or</div>
            <div><input type="submit" name="btn-show-upload-input" id="btn-show-upload-input" value="Upload" class="convert-button activate-button" /></div>
          </form>
        </div>
      </div>
      <div id="web-convert-modal" class="modal fade" role="dialog">
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <button type="button" class="close" data-dismiss="modal">&times;</button>
              <h4 class="modal-title">Convert Scratch projects to Catrobat</h4>
              <div>Quickly turn your Scratch desktop projects into full-fledged mobile Catrobat projects</div>
            </div>
            <div class="modal-body">
              <div>
                <form id="converter_form" action="convert.php" method="post" enctype="multipart/form-data">
                  <p style="font-size:18px;">Enter a Scratch project URL ...</p>
                  <div class="input-field">
                    <input type="text" id="field-url" name="url" value="http://scratch.mit.edu/projects/10205819/" class="clearable" />
                  </div>
                  <div id="field-url-validation-result"></div>
                  <div id="qrcode" style="width:200px;height:200px;margin-top:15px;"></div>
                  <input type="submit" name="submit" id="btn-convert" value="Convert" class="convert-button deactivate-button" />
                </form>
              </div>
              <div class="separator-line"></div>
              <div>
                <h2>How it works</h2>
                <div>
                  <ul>
                    <li>Enter the project URL in the input field above and hit the "Convert" button.</li>
                    <li>After the conversion has finished a QR-Code will be shown.</li>
                    <li>Install and open the PocketCode app on your <a href="https://play.google.com/store/apps/details?id=org.catrobat.catroid" target="_blank">Android</a> or iOS device (coming soon).</li>
                    <li>Now hold your device over the QR Code so that it's clearly visible within your smartphone's screen.</li>
                    <li>Your project should subsequently open on your mobile device.</li>
                    <li>That's it. :)</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div id="upload-convert-modal" class="modal fade" role="dialog">
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <button type="button" class="close" data-dismiss="modal">&times;</button>
              <h4>Convert Scratch projects to Catrobat</h4>
              <div>Please select your locally stored Scratch project (.sb2 file) and hit the <i>Convert</i> button</div>
            </div>
            <div class="modal-body">
              <form id="converter_form" action="convert.php" method="post" enctype="multipart/form-data">
                <div class="input-field">
                  <input type="file" id="field-filename" name="filename" class="size-large input-search" />
                </div>
                <input type="submit" name="submit" id="btn-convert" value="Convert" class="convert-button activate-button" />
              </form>
            </div>
          </div>
        </div>
      </div>
    </article>
  </div>
  <p>&nbsp;</p>
<!--   <footer>
    <div id="footer-menu" class="footer-padding">
      <div>&copy; Copyright 2014 - 2015 Catrobat Team</div>
    </div>
  </footer>
 -->  <p>&nbsp;</p>
  <p>&nbsp;</p>
</body>
</html>
