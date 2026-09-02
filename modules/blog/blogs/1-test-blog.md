Summary
Added a blog module at modules/blog/, following the same pattern as chat/attendance:

Backend — posts and comments tables in their own blog.db; routes for list (/blog), create (/blog/new), view (/blog/<id>), edit (/blog/<id>/edit, author-only), delete (/blog/<id>/delete, author or admin), and comment (/blog/<id>/comment).
Templates — blog_index.html (card list), blog_new.html/blog_edit.html (forms), blog_post.html (post + comment thread), all extending base.html.
Styling — new .blog-* classes appended to style.css matching the existing chat/dashboard look.
Wiring — blueprint registered in app.py, nav box added to the home page.
Next: run the app and click through it in a browser if you want a visual check — I only verified it via Flask's test client.