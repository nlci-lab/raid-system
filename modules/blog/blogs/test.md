comments table dropped, /blog/<id>/comment now 404s (route removed), and the rest of the blog module works normally — /blog loads, and /blog/4 (internal post) still correctly redirects a viewer-tier session, confirming nothing else broke.

Removed:

DB: comments table (1 existing comment was deleted along with it — migration runs automatically on server start).
Backend: add_comment route, comment fetch/cleanup in view_post/delete_post/_sync_posts_with_folder, comment_count subquery in index, unused logged_in template var.
Templates: the entire comments section in blog_post.html, comment-count line in blog_index.html.
CSS: all .blog-comment* rules in style.css.
Server's restarted and running with the change live.