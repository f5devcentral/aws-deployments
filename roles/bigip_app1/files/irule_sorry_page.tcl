when HTTP_REQUEST {
  set VSPool [LB::server pool]
  if { [active_members $VSPool] < 1 } {
    log local0. "Client [IP::client_addr] requested [HTTP::uri] no active nodes available..."
    if { [HTTP::uri] ends_with "sorry.png" } {
      HTTP::respond 200 content [b64decode [class element -name 0 sorry_images]] "Content-Type" "image/png"
    } else {
      if { [HTTP::uri] ends_with "background.png" } {
        HTTP::respond 200 content [b64decode [class element -name 0 background_images]] "Content-Type" "image/png"
      } else {
        HTTP::respond 200 content "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">
<html xml:lang=\"en\" xmlns=\"http://www.w3.org/1999/xhtml\" lang=\"en\"><head>

    <meta http-equiv=\"Content-Type\" content=\"text/html; charset=UTF-8\">
    <title>Oouchhh!</title>


<style type=\"text/css\">
body {
    background: #f7f4f1 url(background.png) repeat top left;
}

#MainContent {
    background: url(sorry.png) no-repeat top right;
    height: 500px;
    font-family: Verdana, Helvetica, Arial, sans;
    font-size: 14px;
    color: #625746;
    position: absolute;
    top: 100px;
    left: 80px;
    width: 800px;
}

#MainContent p {
    width: 450px;
}

a {
    color:#60A2B9;
}
a:hover {
    text-decoration: none;
}
</style>
</head><body>
    <div id=\"MainContent\">
        <p><strong>Ouchhhhh! Snap! Something went terribly wrong!!!</strong></p>
        <p>In the mean while, go <a href=\"http://www.funnyordie.com\">here</a> to entertain yourself while we figure out what just happened :-)</p>

        <p>Wish us luck!</p>
    </div>
</body></html>"
      }
    }
  }
}
