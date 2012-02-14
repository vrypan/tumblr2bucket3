#! /usr/bin/env python

# tumblr2html
# Copyright 2012 Panayotis Vryonis 
# http://vrypan.net/
# License: MIT.

import json
import urllib
import urllib2
import urlparse
import os
from jinja2 import Template, FileSystemLoader, Environment

import re
from datetime import date
import argparse
import shutil

def remove_html_tags(data):
	p = re.compile(r'<.*?>')
	return p.sub('', data)

class tumblr2bucket3(object):
	def __init__(self, 
			tumblr_api_key=None, 
			blog=None, 
			html_path=None, 
			cont=False,
			templates_dir='./templates'):		
		self.tumblr_api_key = tumblr_api_key
		self.blog = blog
		self.html_path = html_path
		self.index = []
		self.total_posts = 0
		self.rendered_posts = 0
		self.last_post_id = 0
		self.min_id = 0 # Do not render posts with ID <= than this. Used when --continue is selected
		self.cont = cont # True if --contine is selected
		
		if cont:
			self.get_conf()

		if not self.tumblr_api_key:
			self.init_ok = False
			return
		if not self.blog:
			self.init_ok = False
			return
		if not self.html_path:
			self.init_ok = False
			return
		self.init_ok = True
		
		self.get_blog_info()
		
		self.ppp = 10 # posts per page
		(self.total_pages,res) = divmod(self.total_posts, self.ppp)

		self.tpl_env = Environment(loader=FileSystemLoader(templates_dir))
		
	def get_blog_info(self):
		request_url = 'http://api.tumblr.com/v2/blog/%s/info?api_key=%s' % (self.blog, self.tumblr_api_key)
		response = urllib.urlopen(request_url)
		json_response = json.load(response)
		self.blog_info = json_response['response']['blog']
		self.total_posts = json_response['response']['blog']['posts']

	def get_conf(self):
		try:
			f = open(os.path.join(self.html_path,'.tumblr2html.json'), 'r')
			data = json.load(f)
			if data['blog']:
				self.blog = data['blog']
			if data['last_post_id']:
				self.min_id = data['last_post_id']
			f.close()
		except IOError:
			pass

	def get_total_posts(self):
		if self.total_posts:
			return self.total_posts
		else:
			self.get_blog_info()
			return self.total_posts
			
	def render_text_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,"%s.html" % p['id'] )
		if not os.path.exists(path):
			os.makedirs(path)

		#if not p['title']:
		#	p['title'] = remove_html_tags(p['body'])[0:140]

		# locate any links to uploaded images, make a local copy, 
		# and replace remote links with local
		img_links = re.findall(r'img src=[\'"]?([^\'" ]+)', p['body'])
		p['attached'] = []
		for i, img in enumerate(img_links):
			img_extension = os.path.splitext(img)[1][1:]
			img_filename = "img_%s.%s" % (i, img_extension) 
			img_file = os.path.join(path, img_filename)
			remote_file = urllib2.urlopen(img)
			local = open(img_file,'wb')
			local.write(remote_file.read())
			local.close()
			p['body'] = p['body'].replace(img,img_filename)
			p['attached'].append(img_filename)
		
		tpl = self.tpl_env.get_template('text.html')
		html = tpl.render(post=p, blog=b)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()
		print "[text]", path
		
	def render_photo_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,"%s.html" % p['id'] )
		if not os.path.exists(path):
			os.makedirs(path)
		
		for i,photo in enumerate(p['photos']):			
			# get the original file extension. Kind of a hack, since the original photo is returned without an extension.
			extension = os.path.splitext(photo['alt_sizes'][-1]['url'])[1][1:] 
			img_filename = "%s_original.%s" % (i, extension) 
			img_file = os.path.join(path, img_filename)
			remote_file = urllib2.urlopen(photo['original_size']['url'])
			local = open(img_file,'wb')
			local.write(remote_file.read())
			local.close()
			photo['original_size']['url'] = os.path.join('img',img_filename)

			prev_i = 0
			prev_w = 0
			prev_h = 0

			for alt in photo['alt_sizes']:
				img_filename = "%s_%sx%s.%s" % (i, alt['width'], alt['height'], extension) 
				img_file = os.path.join(path, img_filename)
				remote_file = urllib2.urlopen(alt['url'])
				local = open(img_file,'wb')
				local.write(remote_file.read())
				local.close()
				alt['url'] = img_filename
				if alt['width']<401 and alt['width']>prev_w:
					prev_url = alt['url']
					prev_w = alt['width']
					prev_h = alt['height']

			photo['prev'] = {'url':prev_url, 'width': prev_w, 'height':prev_h }

		tpl = self.tpl_env.get_template('photo.html')
		html = tpl.render(post=p, blog=b)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		print "[photo]", path
		
	def render_link_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,"%s.html" % p['id'] )
		if not os.path.exists(path):
			os.makedirs(path)
		tpl = self.tpl_env.get_template('link.html')
		html = tpl.render(post=p, blog=b)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		print "[link]", path

	def render_quote_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,"%s.html" % p['id'] )
		if not os.path.exists(path):
			os.makedirs(path)
		tpl = self.tpl_env.get_template('quote.html')
		html = tpl.render(post=p, blog=b)
		
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		p['title'] = 'quote'

		print "[quote]", path

	def render_chat_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,"%s.html" % p['id'] )
		if not os.path.exists(path):
			os.makedirs(path)
		tpl = self.tpl_env.get_template('chat.html')
		html = tpl.render(post=p, blog=b)
		
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		print "[chat]", path

	def render_video_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,"%s.html" % p['id'] )
		if not os.path.exists(path):
			os.makedirs(path)
		video_link = re.findall(r'(http://api\.tumblr\.com/video_file/[^\'"]+)[\'"]\,([0-9]+)\,([0-9]+)\,[\'"]poster=([^,]+)', p['player'][1]['embed_code'])
		if video_link:
			video_filename = "%s.mp4" % p['id'] 
			video_file = os.path.join(path, video_filename)
			print "Downloading %s" % video_file
			remote_file = urllib2.urlopen(video_link[0][0])
			local = open(video_file,'wb')
			local.write(remote_file.read())
			local.close()
			
			poster_filename = "%s.jpeg" % p['id']
			poster_file = os.path.join(path, poster_filename)
			print "Downloading %s" % poster_file
			remote_file = urllib2.urlopen(urllib.unquote(video_link[0][3]))
			local = open(poster_file,'wb')
			local.write(remote_file.read())
			local.close()
			
			p['local_video'] = video_filename
			p['local_poster'] = poster_filename
			p['local_video_width'] = video_link[0][1]
			p['local_video_height'] = video_link[0][2]
			
		tpl = self.tpl_env.get_template('video.html')
		html = tpl.render(post=p, blog=b)
		
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		p['title'] = 'video'

		print "[video]", path

	def render_post(self, post, blog):
		if post['type'] == 'text' :
			self.render_text_post(post, blog)
		elif post['type'] == 'photo':
			self.render_photo_post(post, blog)
		elif post['type'] == 'link':
			self.render_link_post(post, blog)
		elif post['type'] == 'quote':
			self.render_quote_post(post, blog)
		elif post['type'] == 'chat':
			self.render_chat_post(post, blog)
		elif post['type'] == 'video':
			self.render_video_post(post, blog)
		else:
			return
		
	def render_20posts(self,offset=0, limit=20):
		request_url = 'http://api.tumblr.com/v2/blog/%s/posts?api_key=%s&offset=%s&limit=%s' % (self.blog, self.tumblr_api_key, offset, limit)
		response = urllib.urlopen(request_url)
		json_response = json.load(response)
		if json_response['meta']['status'] == 200:
			for p in json_response['response']['posts']:
				if self.cont and p['id'] <= self.min_id:
					self.last_post_id = self.min_id
					return False
				if self.last_post_id < p['id']:
					self.last_post_id = p['id']
				self.render_post(post=p, blog=json_response['response']['blog'])
				self.rendered_posts = self.rendered_posts +1 
		return True

	def render_posts(self):
		total = self.get_total_posts()
		pages,posts_to_render = divmod(total, self.ppp)
		
		print "total posts=%s, pages=%s, posts_to_render=%s" % (total, pages, posts_to_render)
		
		# 1st time is special case. Instead of creating a page with few results, we add them to the palst page.
		if pages>0 :
			posts_to_render = posts_to_render + self.ppp 
		else:
			pages=1
			
		offset = 0
		
		for page in range(pages,0,-1):
			print "offset=%s, posts=%s, page=%s" % (offset, posts_to_render, page)
			ret = self.render_20posts(offset,posts_to_render)
			if not ret:
				break
			offset = offset + posts_to_render
			posts_to_render = self.ppp

		data = {'last_post_id': self.last_post_id, 'blog':self.blog}
		f = open(os.path.join(self.html_path,'.tumblr2html.json'), 'w')
		f.write(json.dumps(data))
		f.close()


def main(*argv):
	parser = argparse.ArgumentParser(description="usage: tumblr2html.py [options]", prefix_chars='-+')
	parser.add_argument("-k", "--api-key",
		dest="api_key",
		help="tumblr api key. See http://www.tumblr.com/oauth/apps")
	parser.add_argument("-b", "--blog",
		dest="blog",
		help="tumblr blog, ex. 'blog.vrypan.net' or 'engineering.tumblr.com'")
	parser.add_argument("-p", "--path",
		dest="path",
		help="destination path for generated HTML")
	parser.add_argument("-c", "--continue",
		action="store_true", default=False,
		dest="cont",
		help="only download new posts since last backup [does nothing yet]")
	parser.add_argument("-t", "--template-dir",
		dest="templates_dir",
		help="templates dir")


	args = parser.parse_args()
	
	t2b = tumblr2bucket3(
		tumblr_api_key=args.api_key, 
		blog=args.blog, 
		html_path=args.path, 
		cont=args.cont,
		templates_dir = args.templates_dir)
	if not t2b.init_ok:
		parser.print_help()
	else:
		t2b.render_posts()
	
if __name__ == '__main__':
	main()
