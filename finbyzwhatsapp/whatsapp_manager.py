from __future__ import unicode_literals
import frappe, os, sys, time, json, tempfile, shutil, datetime
# from frappe.utils.pdf import get_pdf
from finbyzerp.print_format import get_pdf
from frappe.utils.file_manager import save_file
from frappe.utils.background_jobs import enqueue
from frappe import _

from PIL import Image
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.firefox.options import Options
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException


@frappe.whitelist()
def get_whatsapp_settings():
	if frappe.db.get_value("System Settings","System Settings","enable_whatsapp") == '1':
		return True

@frappe.whitelist()
def whatsapp_login_check(doctype,name):
	profiledir = os.path.join(".", "firefox_cache")
	if not os.path.exists(profiledir):
		os.makedirs(profiledir)

	profile = webdriver.FirefoxProfile(profiledir)
	profile.set_preference("browser.cache.disk.enable",True)
	profile.set_preference("browser.cache.memory.enable", True)
	profile.set_preference("browser.cache.offline.enable", True)
	profile.set_preference("network.http.use-cache", True)
	profile.update_preferences()
	options = Options()
	options.headless = True
	options.profile = profile
	options.add_argument("disable-infobars")
	options.add_argument("--disable-extensions")
	options.add_argument('--no-sandbox')
	options.add_argument('--disable-gpu')
	options.add_argument("--disable-dev-shm-usage")
	# options.add_argument("--disable-default-apps")
	# options.add_argument("--disable-crash-reporter")
	# options.add_argument("--disable-in-process-stack-traces")
	# options.add_argument("--disable-login-animations")
	options.add_argument("--no-default-browser-check")
	# options.add_argument("--disable-notifications")
	driver = webdriver.Firefox(options=options,executable_path="/usr/local/bin/geckodriver")
	driver.get('https://web.whatsapp.com/')
	loggedin = False

	local_storage_file = os.path.join(profiledir, "{}.json".format(frappe.session.user))
	if os.path.exists(local_storage_file):
		with open(local_storage_file) as f:
			data = json.loads(f.read())
			driver.execute_script(
			"".join(
				[
					"window.localStorage.setItem('{}', '{}');".format(
						k, v.replace("\n", "\\n") if isinstance(v, str) else v
					)
					for k, v in data.items()
				]
			))
		driver.refresh()
		
	try:
		WebDriverWait(driver, 300).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.two' + ',' + 'canvas')))
	except:
		ss_name_first =  'whatsapp error ' + frappe.session.user + 'first' +  frappe.generate_hash(length=5) +'.png'
		f_first = save_file(ss_name_first, '', '','')
		driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_first.file_name)
		error_log_first = frappe.log_error(frappe.get_traceback(),"Unable to connect your whatsapp")
		f_first.db_set('attached_to_doctype','Error Log')
		f_first.db_set('attached_to_name',error_log_first.name)
		frappe.db.commit()
		driver.quit()
		return False

	# SS start
	# driver_ss_dir = os.path.join("./driver_ss/", "{}".format(frappe.session.user))
	# if not os.path.exists(driver_ss_dir):
	# 	os.makedirs(driver_ss_dir)
	# image_path = frappe.utils.get_bench_path() + '/sites/driver_ss/{}/driver_sec.png'.format(frappe.session.user)
	# driver.save_screenshot(image_path)
	# SS end
	try:
		driver.find_element_by_css_selector('.two')
		loggedin = True
	except NoSuchElementException:
		driver.find_element_by_css_selector('canvas')
	except:
		ss_name_second =  'whatsapp error ' + frappe.session.user + 'second' + frappe.generate_hash(length=5) + '.png'
		f_second = save_file(ss_name_second, '', '','')
		driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_second.file_name)
		error_log_second = frappe.log_error(frappe.get_traceback(),"Unable to connect your whatsapp")
		f_second.db_set('attached_to_doctype','Error Log')
		f_second.db_set('attached_to_name',error_log_second.name)
		frappe.db.commit()
		driver.quit()
		return False

	if not loggedin:
		qr_hash = frappe.generate_hash(length = 15)
		path_private_files = frappe.get_site_path('public','files') + '/{}.png'.format(frappe.session.user + qr_hash)
		try:
			driver.find_element_by_css_selector('._1a-np')
			driver.find_element_by_name('rememberMe').click()
		except:
			pass
		try:
			WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'canvas')))
		except:
			ss_name_third =  'whatsapp error ' + frappe.session.user + 'third' + frappe.generate_hash(length=5) +'.png'
			f_third = save_file(ss_name_third, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_third.file_name)
			error_log_third = frappe.log_error(frappe.get_traceback(),"Unable to generate QRCode in Whatsapp")
			f_third.db_set('attached_to_doctype','Error Log')
			f_third.db_set('attached_to_name',error_log_third.name)
			frappe.db.commit()
			driver.quit()
			return False

		try:
			driver.find_element_by_css_selector("div[data-ref] > span > div").click()
		except:
			pass

		qr = driver.find_element_by_css_selector('canvas')
		fd = os.open(path_private_files, os.O_RDWR | os.O_CREAT)
		fn_png = os.path.abspath(path_private_files)
		qr.screenshot(fn_png)

		msg = "<img src='/files/{}.png' alt='No Image' data-pagespeed-no-transform>".format(frappe.session.user + qr_hash)
		event = str(frappe.session.user + doctype + name)
		frappe.publish_realtime(event=event, message=msg,user=frappe.session.user,doctype=doctype,docname=name)

		try:
			WebDriverWait(driver, 300).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.two')))
		except:
			ss_name_fourth =  'whatsapp error ' + frappe.session.user + 'fourth' + frappe.generate_hash(length=5) + '.png'
			f_fourth = save_file(ss_name_fourth, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_fourth.file_name)
			error_log_fourth = frappe.log_error(frappe.get_traceback(),"Unable to Save Profile in whatsapp")
			f_fourth.db_set('attached_to_doctype','Error Log')
			f_fourth.db_set('attached_to_name',error_log_fourth.name)
			frappe.db.commit()
			driver.quit()
			remove_qr_code(qr_hash)
			return False

		for item in os.listdir(profile.path):
			if item in ["parent.lock", "lock", ".parentlock"]:
				continue

			s = os.path.join(profile.path, item)
			if item.endswith('{}.json'.format(frappe.session.user)):
				profiles_json_list = [pos_json for pos_json in os.listdir(profiledir) if pos_json.endswith('.json')]
				if profiles_json_list:
					mobile_number_dict = {}
					for f_item in profiles_json_list:
						with open(os.path.join(profiledir,f_item), "r") as existsf:
							file_r = json.loads(existsf.read())
							mobile_number_dict.setdefault(f_item,str(file_r.get('last-wid')))
						
				if mobile_number_dict:
					with open(s,"r") as tempf: 
						read = json.loads(tempf.read())
						for key,value in mobile_number_dict.items():
							if value == str(read.get('last-wid')) and key.find(frappe.session.user) == -1:
								frappe.log_error("Profile Already Exists for '{}' with user  = '{}'".format(frappe.bold(value.split('@')[0]),frappe.bold(key.split('.json')[0])),"Whatsapp Error")
								driver.quit()
								remove_qr_code(qr_hash)
								frappe.throw("Profile Already Exists for '{}' with user  = '{}'".format(frappe.bold(value.split('@')[0]),frappe.bold(key.split('.json')[0])))
								return False

		try:
			for item in os.listdir(profile.path):
				if item in ["parent.lock", "lock", ".parentlock"]:
					continue

				s = os.path.join(profile.path, item)
				d = os.path.join(profiledir, item)
				if os.path.isdir(s):
					shutil.copytree(
						s,
						d,
						ignore=shutil.ignore_patterns(
							"parent.lock", "lock", ".parentlock"
						),
					)
				else:
					shutil.copy2(s, d)

			with open(os.path.join(profiledir,"{}.json".format(frappe.session.user)), "w") as f:
				f.write(json.dumps(driver.execute_script("return window.localStorage;")))

			time.sleep(10)
			driver.quit()
			return [qr_hash]
		except:
			ss_name_fifth =  'whatsapp error ' + frappe.session.user + 'fifth' + frappe.generate_hash(length=5) + '.png'
			f_fifth = save_file(ss_name_fifth, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_fifth.file_name)
			error_log_fifth = frappe.log_error(frappe.get_traceback(),"Unable to Save Profile in whatsapp")
			f_fifth.db_set('attached_to_doctype','Error Log')
			f_fifth.db_set('attached_to_name',error_log_fifth.name)
			frappe.db.commit()
			driver.quit()
			remove_qr_code(qr_hash)
			return False
	else:
		driver.quit()
		return True
			
@frappe.whitelist()
def get_pdf_whatsapp(doctype,name,attach_document_print,print_format,selected_attachments,mobile_number,description):
	selected_attachments = json.loads(selected_attachments)
	attach_document_print = json.loads(attach_document_print)

	if mobile_number.find(" ") != -1:
		mobile_number = mobile_number.replace(" ","")
	if mobile_number.find("+") != -1:
		mobile_number = mobile_number.replace("+","")
	if mobile_number[0] == '9' and mobile_number[1] == '1' and len(mobile_number[2:]) == 10:
		mobile_number = mobile_number[2:]
	if len(mobile_number) != 10:
		frappe.throw("Please Enter Only 10 Digit Contact Number.")

	# login_or_not = whatsapp_login_check(doctype,name)
	# qr_hash = False
	# if isinstance(login_or_not,list):
	# 	driver = login_or_not[0]
	# 	try:
	# 		qr_hash = login_or_not[1]
	# 	except:
	# 		pass
	# elif login_or_not == False:
	# 	return False
	# background_msg_whatsapp(driver,qr_hash,doctype,name,attach_document_print,print_format,selected_attachments,mobile_number,description)
	enqueue(background_msg_whatsapp,queue= "long", timeout= 1800, job_name= 'Whatsapp Message', doctype= doctype, name= name, attach_document_print=attach_document_print,print_format= print_format,selected_attachments=selected_attachments,mobile_number=mobile_number,description=description)

def background_msg_whatsapp(doctype,name,attach_document_print,print_format,selected_attachments,mobile_number,description):
	if attach_document_print==1:
		html = frappe.get_print(doctype=doctype, name=name, print_format=print_format)
		filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
		filecontent = get_pdf(html)

		file_data = save_file(filename, filecontent, doctype,name,is_private=1)
		file_url = file_data.file_url
		site_path = frappe.get_site_path('private','files') + "/{}".format(filename)
		send_msg = send_media_whatsapp(mobile_number,description,selected_attachments,doctype,name,print_format,site_path)
		
		remove_file_from_os(site_path)
		frappe.db.sql("delete from `tabFile` where file_name='{}'".format(filename))
		frappe.db.sql("delete from `tabComment` where reference_doctype='{}' and reference_name='{}' and comment_type='Attachment' and comment_email = '{}' and content LIKE '%{}%'".format(doctype,name,frappe.session.user,file_url))

	else:
		send_msg = send_media_whatsapp(mobile_number,description,selected_attachments,doctype,name,print_format)

	if selected_attachments:
		for f_name in selected_attachments:
			attach_url = frappe.get_site_path() + str(frappe.db.get_value('File',f_name,'file_url'))
			remove_file_from_os(attach_url)
			frappe.db.sql("delete from `tabFile` where name='{}'".format(f_name))
	# if qr_hash:
	# 	remove_qr_code(qr_hash)

	if not send_msg == False:
		comment_whatsapp = frappe.new_doc("Comment")
		comment_whatsapp.comment_type = "WhatsApp"
		comment_whatsapp.comment_email = frappe.session.user
		comment_whatsapp.reference_doctype = doctype
		comment_whatsapp.reference_name = name
		if attach_document_print==1:
			comment_whatsapp.content = "Have Sent the Whatsapp Message: <b>'{}'</b> to <b>{}</b> with Print <b>'{}'</b>".format(description,mobile_number,print_format)
		else:
			comment_whatsapp.content = "Have Sent the Whatsapp Message: <b>'{}'</b> to <b>{}</b>".format(description,mobile_number)

		comment_whatsapp.save(ignore_permissions=True)

	return "Success"

	
def send_media_whatsapp(mobile_number,description,selected_attachments,doctype,name,print_format,site_path=None):

	if len(mobile_number) == 10:
		mobile_number = "91" + mobile_number

	profiledir = os.path.join("./profiles/", "{}".format(frappe.session.user))
	if not os.path.exists(profiledir):
		os.makedirs(profiledir)

	options = webdriver.ChromeOptions()
	options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36")
	options.add_argument("--headless")
	options.add_argument("user-data-dir={}".format(os.path.join("./profiles/", "{}".format(frappe.session.user))))
	options.add_argument("--disable-infobars")
	options.add_argument("--disable-extensions")
	options.add_argument("--disable-crash-reporter")
	options.add_argument('--no-sandbox')
	options.add_argument('--disable-gpu')
	options.add_argument("--disable-dev-shm-usage")
	options.add_argument("--no-default-browser-check")
	driver = webdriver.Chrome(options=options,executable_path="/usr/local/bin/chromedriver")
	driver.get('https://web.whatsapp.com/')
	loggedin = False

	try:
		WebDriverWait(driver, 300).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.two' + ',' + 'canvas')))
	except:
		ss_name_first =  'whatsapp error ' + frappe.session.user + 'first' +  frappe.generate_hash(length=5) +'.png'
		# f_first = save_file(ss_name_first, '', '','')
		driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ss_name_first)
		error_log_first = frappe.log_error(frappe.get_traceback(),"Unable to connect your whatsapp in {} : {}".format(doctype,name))
		f_first = frappe.new_doc("File")
		f_first.file_url = "/files/"+ss_name_first
		f_first.attached_to_doctype = 'Error Log'
		f_first.attached_to_name = error_log_first.name
		f_first.flags.ignore_permissions = True
		f_first.insert()
		frappe.db.commit()
		driver.quit()
		return False


	try:
		driver.find_element_by_css_selector('.two')
		loggedin = True
	except NoSuchElementException:
		element = driver.find_element_by_css_selector('canvas')
	except:
		ss_name_second =  'whatsapp error ' + frappe.session.user + 'second' + frappe.generate_hash(length=5) + '.png'
		# f_second = save_file(ss_name_second, '', '','')
		driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_second)
		error_log_second = frappe.log_error(frappe.get_traceback(),"Unable to connect your whatsapp in {} : {}".format(doctype,name))
		f_second = frappe.new_doc("File")
		f_second.file_url = "/files/"+ss_name_second
		f_second.attached_to_doctype = 'Error Log'
		f_second.attached_to_name = error_log_second.name
		f_second.flags.ignore_permissions = True
		f_second.insert()
		frappe.db.commit()
		driver.quit()
		return False

	if not loggedin:
		qr_hash = frappe.generate_hash(length = 15)
		path_private_files = frappe.get_site_path('public','files') + '/{}.png'.format(frappe.session.user + qr_hash)
		try:
			driver.find_element_by_css_selector('._1a-np')
			driver.find_element_by_name('rememberMe').click()
		except:
			pass
		try:
			WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'canvas')))
		except:
			ss_name_third =  'whatsapp error ' + frappe.session.user + 'third' + frappe.generate_hash(length=5) +'.png'
			# f_third = save_file(ss_name_third, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_third)
			error_log_third = frappe.log_error(frappe.get_traceback(),"Unable to generate QRCode in whatsapp in {} : {}".format(doctype,name))
			f_third = frappe.new_doc("File")
			f_third.file_url = "/files/"+ss_name_third
			f_third.attached_to_doctype = 'Error Log'
			f_third.attached_to_name = error_log_third.name
			f_third.flags.ignore_permissions = True
			f_third.insert()
			frappe.db.commit()
			driver.quit()
			return False

		try:
			driver.find_element_by_css_selector("div[data-ref] > span > div").click()
		except:
			pass

		# qr = driver.find_element_by_css_selector('canvas')
		# fd = os.open(path_private_files, os.O_RDWR | os.O_CREAT)
		# fn_png = os.path.abspath(path_private_files)
		# qr.screenshot(fn_png)

		png = driver.get_screenshot_as_png()
		qr = Image.open(BytesIO(png))
		qr = qr.crop((element.location['x'], element.location['y'], element.location['x'] + element.size['width'], element.location['y'] + element.size['height']))
		qr.save(path_private_files)
		msg = "<img src='/files/{}.png' alt='No Image' data-pagespeed-no-transform>".format(frappe.session.user + qr_hash)
		event = str(frappe.session.user + doctype + name)
		frappe.publish_realtime(event=event, message=msg,user=frappe.session.user,doctype=doctype,docname=name)

		try:
			WebDriverWait(driver, 300).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.two')))
		except:
			ss_name_fourth =  'whatsapp error ' + frappe.session.user + 'fourth' + frappe.generate_hash(length=5) + '.png'
			# f_fourth = save_file(ss_name_fourth, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_fourth)
			error_log_fourth = frappe.log_error(frappe.get_traceback(),"Unable to Save Profile in whatsapp in {} : {}".format(doctype,name))
			f_fourth = frappe.new_doc("File")
			f_fourth.file_url = "/files/"+ss_name_fourth
			f_fourth.attached_to_doctype = 'Error Log'
			f_fourth.attached_to_name = error_log_fourth.name
			f_fourth.flags.ignore_permissions = True
			f_fourth.insert()
			frappe.db.commit()
			driver.quit()
			remove_qr_code(qr_hash)
			return False

		# for item in os.listdir(profile.path):
		# 	if item in ["parent.lock", "lock", ".parentlock"]:
		# 		continue

		# 	s = os.path.join(profile.path, item)
		# 	if item.endswith('{}.json'.format(frappe.session.user)):
		# 		profiles_json_list = [pos_json for pos_json in os.listdir(profiledir) if pos_json.endswith('.json')]
		# 		if profiles_json_list:
		# 			mobile_number_dict = {}
		# 			for f_item in profiles_json_list:
		# 				with open(os.path.join(profiledir,f_item), "r") as existsf:
		# 					file_r = json.loads(existsf.read())
		# 					mobile_number_dict.setdefault(f_item,str(file_r.get('last-wid')))
						
		# 		if mobile_number_dict:
		# 			with open(s,"r") as tempf: 
		# 				read = json.loads(tempf.read())
		# 				for key,value in mobile_number_dict.items():
		# 					if value == str(read.get('last-wid')) and key.find(frappe.session.user) == -1:
		# 						frappe.log_error("Profile Already Exists for '{}' with user  = '{}'".format(frappe.bold(value.split('@')[0]),frappe.bold(key.split('.json')[0])),"Whatsapp Error")
		# 						driver.quit()
		# 						remove_qr_code(qr_hash)
		# 						# frappe.throw("Profile Already Exists for '{}' with user  = '{}'".format(frappe.bold(value.split('@')[0]),frappe.bold(key.split('.json')[0])))
		# 						return False

		# try:
		# 	for item in os.listdir(profile.path):
		# 		if item in ["parent.lock", "lock", ".parentlock"]:
		# 			continue

		# 		s = os.path.join(profile.path, item)
		# 		d = os.path.join(profiledir, item)
		# 		if os.path.isdir(s):
		# 			shutil.copytree(
		# 				s,
		# 				d,
		# 				ignore=shutil.ignore_patterns(
		# 					"parent.lock", "lock", ".parentlock"
		# 				),
		# 			)
		# 		else:
		# 			shutil.copy2(s, d)

		# 	with open(os.path.join(profiledir,"{}.json".format(frappe.session.user)), "w") as f:
		# 		f.write(json.dumps(driver.execute_script("return window.localStorage;")))
				
			# time.sleep(10)
			# driver.quit()
			# return [qr_hash]
		# except:
		# 	ss_name_fifth =  'whatsapp error ' + frappe.session.user + 'fifth' + frappe.generate_hash(length=5) + '.png'
		# 	f_fifth = save_file(ss_name_fifth, '', '','')
		# 	driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_fifth.file_name)
		# 	error_log_fifth = frappe.log_error(frappe.get_traceback(),"Unable to Save Profile.")
		# 	f_fifth.db_set('attached_to_doctype','Error Log')
		# 	f_fifth.db_set('attached_to_name',error_log_fifth.name)
		# 	frappe.db.commit()
		# 	driver.quit()
		# 	remove_qr_code(qr_hash)
		# 	return False


	link = "https://web.whatsapp.com/send?phone='{}'&text&source&data&app_absent".format(mobile_number)
	driver.get(link)
	
	attach_list = []
	if site_path:
		attach_list.append(site_path)

	if selected_attachments:
		for file_name in selected_attachments:
			attach_url = frappe.get_site_path() + str(frappe.db.get_value('File',file_name,'file_url'))
			attach_list.append(attach_url)

	if description:
		try:
			WebDriverWait(driver, 120).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '._1LbR4')))
		except:
			ss_name_sixth_1 = 'whatsapp error ' + frappe.session.user + 'sixth 1' + frappe.generate_hash(length=5) +  '.png'
			# f_sixth_1 = save_file(ss_name_sixth_1, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_sixth_1)
			error_log_sixth_1 = frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message in {} : {}".format(doctype,name))
			f_sixth_1 = frappe.new_doc("File")
			f_sixth_1.file_url = "/files/"+ss_name_sixth_1
			f_sixth_1.attached_to_doctype = 'Error Log'
			f_sixth_1.attached_to_name = error_log_sixth_1.name
			f_sixth_1.flags.ignore_permissions = True
			f_sixth_1.insert()
			frappe.db.commit()
			driver.quit()
			return False

		try:
			input_box = driver.find_element_by_css_selector('._1LbR4')
			input_box.send_keys(description)
			driver.find_element_by_css_selector('._1Ae7k').click()
		except:
			ss_name_sixth =  'whatsapp error ' + frappe.session.user + 'sixth' + frappe.generate_hash(length=5) +  '.png'
			# f_sixth = save_file(ss_name_sixth, '', '','')
			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_sixth)
			error_log_sixth = frappe.log_error(frappe.get_traceback(),"Error while trying to send the media file in whatsapp in {} : {}".format(doctype,name))
			f_sixth = frappe.new_doc("File")
			f_sixth.file_url = "/files/"+ss_name_sixth
			f_sixth.attached_to_doctype = 'Error Log'
			f_sixth.attached_to_name = error_log_sixth.name
			f_sixth.flags.ignore_permissions = True
			f_sixth.insert()
			frappe.db.commit()
			driver.quit()
			return False

	if attach_list:
		try:
			for path in attach_list:
				path_url = frappe.utils.get_bench_path() + "/sites" + path[1:]
				try:
					WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'span[data-icon="clip"]')))
				except:
					ss_name_seven =  'whatsapp error ' + frappe.session.user + 'seven' + frappe.generate_hash(length=5) +'.png'
					# f_seven = save_file(ss_name_seven, '', '','')
					driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_seven)
					error_log_seven = frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message in {} : {}".format(doctype,name))
					f_seven = frappe.new_doc("File")
					f_seven.file_url = "/files/"+ss_name_seven
					f_seven.attached_to_doctype = 'Error Log'
					f_seven.attached_to_name = error_log_seven.name
					f_seven.flags.ignore_permissions = True
					f_seven.insert()
					frappe.db.commit()
					driver.quit()
					return False
				try:
					WebDriverWait(driver,60).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'span[data-icon="clip"]')))
				except:
					frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message")
					driver.quit()
					return False					
				driver.find_element_by_css_selector('span[data-icon="clip"]').click()
				attach=driver.find_element_by_css_selector('input[type="file"]')
				attach.send_keys(path_url)
				try:
					WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="app"]/div/div/div[2]/div[2]/span/div/span/div/div/div[2]/span/div/div')))
				except:
					ss_name_eight =  'whatsapp error ' + frappe.session.user + 'eight' + frappe.generate_hash(length=5) +  '.png'
					# f_eight = save_file(ss_name_eight, '', '','')
					driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ ss_name_eight)
					error_log_eight = frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message in {} : {}".format(doctype,name))
					f_eight = frappe.new_doc("File")
					f_eight.file_url = "/files/"+ss_name_eight
					f_eight.attached_to_doctype = 'Error Log'
					f_eight.attached_to_name = error_log_eight.name
					f_eight.flags.ignore_permissions = True
					f_eight.insert()
					frappe.db.commit()
					driver.quit()
					return False

				whatsapp_send_button = driver.find_element_by_xpath('//*[@id="app"]/div/div/div[2]/div[2]/span/div/span/div/div/div[2]/span/div/div')
				whatsapp_send_button.click()
	
		except:
			frappe.log_error(frappe.get_traceback(),"Error while trying to send the whatsapp message.")
			return False
	time.sleep(20)
	driver.quit()

def remove_file_from_os(path):
	if os.path.exists(path):
		os.remove(path)
	
def remove_qr_code(qr_hash):
	qr_path = frappe.get_site_path('public','files') + "/{}.png".format(frappe.session.user + qr_hash)
	remove_file_from_os(qr_path)

# def remove_user_profile():
# 	profiledir = os.path.join("./profiles/", "{}".format(frappe.session.user))
# 	if os.path.exists(profiledir):
# 		shutil.rmtree(profiledir)






































# ##without background_jobs below code

# from __future__ import unicode_literals
# import frappe, os, sys, time, json, tempfile, shutil, datetime
# from frappe.utils.pdf import get_pdf
# from frappe.utils.file_manager import save_file
# from frappe.utils.background_jobs import enqueue
# from frappe import _

# from PIL import Image
# from io import BytesIO
# from selenium import webdriver
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support.ui import Select
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.firefox.options import Options
# # from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
# from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
# from selenium.common.exceptions import NoSuchElementException, TimeoutException


# @frappe.whitelist()
# def get_whatsapp_settings():
# 	if frappe.db.get_value("System Settings","System Settings","enable_whatsapp") == '1':
# 		return True

# @frappe.whitelist()
# def whatsapp_login_check(doctype,name):
# 	profiledir = os.path.join(".", "firefox_cache")
# 	if not os.path.exists(profiledir):
# 		os.makedirs(profiledir)

# 	profile = webdriver.FirefoxProfile(profiledir)
# 	profile.set_preference("browser.cache.disk.enable",True)
# 	profile.set_preference("browser.cache.memory.enable", True)
# 	profile.set_preference("browser.cache.offline.enable", True)
# 	profile.set_preference("network.http.use-cache", True)
# 	profile.update_preferences()
# 	options = Options()
# 	options.headless = True
# 	options.profile = profile
# 	options.add_argument("disable-infobars")
# 	options.add_argument("--disable-extensions")
# 	options.add_argument('--no-sandbox')
# 	options.add_argument('--disable-gpu')
# 	options.add_argument("--disable-dev-shm-usage")
# 	# options.add_argument("--disable-default-apps")
# 	# options.add_argument("--disable-crash-reporter")
# 	# options.add_argument("--disable-in-process-stack-traces")
# 	# options.add_argument("--disable-login-animations")
# 	options.add_argument("--no-default-browser-check")
# 	# options.add_argument("--disable-notifications")
# 	driver = webdriver.Firefox(options=options,executable_path="/usr/local/bin/geckodriver")
# 	driver.get('https://web.whatsapp.com/')
# 	loggedin = False

# 	local_storage_file = os.path.join(profiledir, "{}.json".format(frappe.session.user))
# 	if os.path.exists(local_storage_file):
# 		with open(local_storage_file) as f:
# 			data = json.loads(f.read())
# 			driver.execute_script(
# 			"".join(
# 				[
# 					"window.localStorage.setItem('{}', '{}');".format(
# 						k, v.replace("\n", "\\n") if isinstance(v, str) else v
# 					)
# 					for k, v in data.items()
# 				]
# 			))
# 		driver.refresh()
		
# 	try:
# 		WebDriverWait(driver, 300).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.two' + ',' + 'canvas')))
# 	except:
# 		ss_name_first =  'whatsapp error ' + frappe.session.user + 'first' +  frappe.generate_hash(length=5) +'.png'
# 		f_first = save_file(ss_name_first, '', '','')
# 		driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_first.file_name)
# 		error_log_first = frappe.log_error(frappe.get_traceback(),"Unable to connect your whatsapp")
# 		f_first.db_set('attached_to_doctype','Error Log')
# 		f_first.db_set('attached_to_name',error_log_first.name)
# 		frappe.db.commit()
# 		driver.quit()
# 		return False

# 	# SS start
# 	# driver_ss_dir = os.path.join("./driver_ss/", "{}".format(frappe.session.user))
# 	# if not os.path.exists(driver_ss_dir):
# 	# 	os.makedirs(driver_ss_dir)
# 	# image_path = frappe.utils.get_bench_path() + '/sites/driver_ss/{}/driver_sec.png'.format(frappe.session.user)
# 	# driver.save_screenshot(image_path)
# 	# SS end
# 	try:
# 		driver.find_element_by_css_selector('.two')
# 		loggedin = True
# 	except NoSuchElementException:
# 		driver.find_element_by_css_selector('canvas')
# 	except:
# 		ss_name_second =  'whatsapp error ' + frappe.session.user + 'second' + frappe.generate_hash(length=5) + '.png'
# 		f_second = save_file(ss_name_second, '', '','')
# 		driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_second.file_name)
# 		error_log_second = frappe.log_error(frappe.get_traceback(),"Unable to connect your whatsapp")
# 		f_second.db_set('attached_to_doctype','Error Log')
# 		f_second.db_set('attached_to_name',error_log_second.name)
# 		frappe.db.commit()
# 		driver.quit()
# 		return False

# 	if not loggedin:
# 		qr_hash = frappe.generate_hash(length = 15)
# 		path_private_files = frappe.get_site_path('public','files') + '/{}.png'.format(frappe.session.user + qr_hash)
# 		try:
# 			driver.find_element_by_css_selector('._1a-np')
# 			driver.find_element_by_name('rememberMe').click()
# 		except:
# 			pass
# 		try:
# 			WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'canvas')))
# 		except:
# 			ss_name_third =  'whatsapp error ' + frappe.session.user + 'third' + frappe.generate_hash(length=5) +'.png'
# 			f_third = save_file(ss_name_third, '', '','')
# 			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_third.file_name)
# 			error_log_third = frappe.log_error(frappe.get_traceback(),"Unable to generate QRCode")
# 			f_third.db_set('attached_to_doctype','Error Log')
# 			f_third.db_set('attached_to_name',error_log_third.name)
# 			frappe.db.commit()
# 			driver.quit()
# 			return False

# 		try:
# 			driver.find_element_by_css_selector("div[data-ref] > span > div").click()
# 		except:
# 			pass

# 		qr = driver.find_element_by_css_selector('canvas')
# 		fd = os.open(path_private_files, os.O_RDWR | os.O_CREAT)
# 		fn_png = os.path.abspath(path_private_files)
# 		qr.screenshot(fn_png)

# 		msg = "<img src='/files/{}.png' alt='No Image' data-pagespeed-no-transform>".format(frappe.session.user + qr_hash)
# 		event = str(frappe.session.user + doctype + name)
# 		frappe.publish_realtime(event=event, message=msg,user=frappe.session.user,doctype=doctype,docname=name)

# 		try:
# 			WebDriverWait(driver, 300).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.two')))
# 		except:
# 			ss_name_fourth =  'whatsapp error ' + frappe.session.user + 'fourth' + frappe.generate_hash(length=5) + '.png'
# 			f_fourth = save_file(ss_name_fourth, '', '','')
# 			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_fourth.file_name)
# 			error_log_fourth = frappe.log_error(frappe.get_traceback(),"Unable to Save Profile.")
# 			f_fourth.db_set('attached_to_doctype','Error Log')
# 			f_fourth.db_set('attached_to_name',error_log_fourth.name)
# 			frappe.db.commit()
# 			driver.quit()
# 			remove_qr_code(qr_hash)
# 			return False

# 		for item in os.listdir(profile.path):
# 			if item in ["parent.lock", "lock", ".parentlock"]:
# 				continue

# 			s = os.path.join(profile.path, item)
# 			if item.endswith('{}.json'.format(frappe.session.user)):
# 				profiles_json_list = [pos_json for pos_json in os.listdir(profiledir) if pos_json.endswith('.json')]
# 				if profiles_json_list:
# 					mobile_number_dict = {}
# 					for f_item in profiles_json_list:
# 						with open(os.path.join(profiledir,f_item), "r") as existsf:
# 							file_r = json.loads(existsf.read())
# 							mobile_number_dict.setdefault(f_item,str(file_r.get('last-wid')))
						
# 				if mobile_number_dict:
# 					with open(s,"r") as tempf: 
# 						read = json.loads(tempf.read())
# 						for key,value in mobile_number_dict.items():
# 							if value == str(read.get('last-wid')) and key.find(frappe.session.user) == -1:
# 								frappe.log_error("Profile Already Exists for '{}' with user  = '{}'".format(frappe.bold(value.split('@')[0]),frappe.bold(key.split('.json')[0])),"Whatsapp Error")
# 								driver.quit()
# 								remove_qr_code(qr_hash)
# 								frappe.throw("Profile Already Exists for '{}' with user  = '{}'".format(frappe.bold(value.split('@')[0]),frappe.bold(key.split('.json')[0])))
# 								return False

# 		try:
# 			for item in os.listdir(profile.path):
# 				if item in ["parent.lock", "lock", ".parentlock"]:
# 					continue

# 				s = os.path.join(profile.path, item)
# 				d = os.path.join(profiledir, item)
# 				if os.path.isdir(s):
# 					shutil.copytree(
# 						s,
# 						d,
# 						ignore=shutil.ignore_patterns(
# 							"parent.lock", "lock", ".parentlock"
# 						),
# 					)
# 				else:
# 					shutil.copy2(s, d)

# 			with open(os.path.join(profiledir,"{}.json".format(frappe.session.user)), "w") as f:
# 				f.write(json.dumps(driver.execute_script("return window.localStorage;")))
			
# 			# driver.quit()
# 			return [driver,qr_hash]
# 		except:
# 			ss_name_fifth =  'whatsapp error ' + frappe.session.user + 'fifth' + frappe.generate_hash(length=5) + '.png'
# 			f_fifth = save_file(ss_name_fifth, '', '','')
# 			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_fifth.file_name)
# 			error_log_fifth = frappe.log_error(frappe.get_traceback(),"Unable to Save Profile.")
# 			f_fifth.db_set('attached_to_doctype','Error Log')
# 			f_fifth.db_set('attached_to_name',error_log_fifth.name)
# 			frappe.db.commit()
# 			driver.quit()
# 			remove_qr_code(qr_hash)
# 			return False
# 	else:
# 		return [driver]
			
# @frappe.whitelist()
# def get_pdf_whatsapp(doctype,name,attach_document_print,print_format,selected_attachments,mobile_number,description):
# 	selected_attachments = json.loads(selected_attachments)
# 	attach_document_print = json.loads(attach_document_print)

# 	if mobile_number.find(" ") != -1:
# 		mobile_number = mobile_number.replace(" ","")
# 	if mobile_number.find("+") != -1:
# 		mobile_number = mobile_number.replace("+","")
# 	if mobile_number[0] == '9' and mobile_number[1] == '1' and len(mobile_number[2:]) == 10:
# 		mobile_number = mobile_number[2:]
# 	if len(mobile_number) != 10:
# 		frappe.throw("Please Enter Only 10 Digit Contact Number.")

# 	login_or_not = whatsapp_login_check(doctype,name)
# 	qr_hash = False
# 	if isinstance(login_or_not,list):
# 		driver = login_or_not[0]
# 		try:
# 			qr_hash = login_or_not[1]
# 		except:
# 			pass
# 	elif login_or_not == False:
# 		return False
# 	background_msg_whatsapp(driver,qr_hash,doctype,name,attach_document_print,print_format,selected_attachments,mobile_number,description)
# 	# enqueue(background_msg_whatsapp,queue= "long", timeout= 1800, job_name= 'Whatsapp Message', doctype= doctype, name= name, attach_document_print=attach_document_print,print_format= print_format,selected_attachments=selected_attachments,mobile_number=mobile_number,description=description)

# def background_msg_whatsapp(driver,qr_hash,doctype,name,attach_document_print,print_format,selected_attachments,mobile_number,description):
# 	if attach_document_print==1:
# 		html = frappe.get_print(doctype=doctype, name=name, print_format=print_format)
# 		filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
# 		filecontent = get_pdf(html)

# 		file_data = save_file(filename, filecontent, doctype,name,is_private=1)
# 		file_url = file_data.file_url
# 		site_path = frappe.get_site_path('private','files') + "/{}".format(filename)
# 		send_msg = send_media_whatsapp(driver,qr_hash,mobile_number,description,selected_attachments,doctype,name,print_format,site_path)
		
# 		remove_file_from_os(site_path)
# 		frappe.db.sql("delete from `tabFile` where file_name='{}'".format(filename))
# 		frappe.db.sql("delete from `tabComment` where reference_doctype='{}' and reference_name='{}' and comment_type='Attachment' and comment_email = '{}' and content LIKE '%{}%'".format(doctype,name,frappe.session.user,file_url))

# 	else:
# 		send_msg = send_media_whatsapp(driver,qr_hash,mobile_number,description,selected_attachments,doctype,name,print_format)

# 	if selected_attachments:
# 		for f_name in selected_attachments:
# 			attach_url = frappe.get_site_path() + str(frappe.db.get_value('File',f_name,'file_url'))
# 			remove_file_from_os(attach_url)
# 			frappe.db.sql("delete from `tabFile` where name='{}'".format(f_name))
# 	if qr_hash:
# 		remove_qr_code(qr_hash)

# 	if not send_msg == False:
# 		comment_whatsapp = frappe.new_doc("Comment")
# 		comment_whatsapp.comment_type = "WhatsApp"
# 		comment_whatsapp.comment_email = frappe.session.user
# 		comment_whatsapp.reference_doctype = doctype
# 		comment_whatsapp.reference_name = name
# 		if attach_document_print==1:
# 			comment_whatsapp.content = "Have Sent the Whatsapp Message: <b>'{}'</b> to <b>{}</b> with Print <b>'{}'</b>".format(description,mobile_number,print_format)
# 		else:
# 			comment_whatsapp.content = "Have Sent the Whatsapp Message: <b>'{}'</b> to <b>{}</b>".format(description,mobile_number)

# 		comment_whatsapp.save(ignore_permissions=True)

# 	return "Success"

	
# def send_media_whatsapp(driver,qr_hash,mobile_number,description,selected_attachments,doctype,name,print_format,site_path=None):

# 	if len(mobile_number) == 10:
# 		mobile_number = "91" + mobile_number

# 	link = "https://web.whatsapp.com/send?phone='{}'&text&source&data&app_absent".format(mobile_number)
# 	driver.get(link)
	
# 	attach_list = []
# 	if site_path:
# 		attach_list.append(site_path)

# 	if selected_attachments:
# 		for file_name in selected_attachments:
# 			attach_url = frappe.get_site_path() + str(frappe.db.get_value('File',file_name,'file_url'))
# 			attach_list.append(attach_url)

# 	if description:
# 		try:
# 			WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="main"]/footer/div[1]/div[2]/div/div[2]')))
# 		except:
# 			ss_name_sixth_1 = 'whatsapp error ' + frappe.session.user + 'sixth 1' + frappe.generate_hash(length=5) +  '.png'
# 			f_sixth_1 = save_file(ss_name_sixth_1, '', '','')
# 			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_sixth_1.file_name)
# 			error_log_sixth_1 = frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message")
# 			f_sixth_1.db_set('attached_to_doctype','Error Log')
# 			f_sixth_1.db_set('attached_to_name',error_log_sixth_1.name)
# 			frappe.db.commit()
# 			driver.quit()
# 			return False

# 		try:
# 			input_box = driver.find_element_by_xpath('//*[@id="main"]/footer/div[1]/div[2]/div/div[2]')
# 			input_box.send_keys(description)
# 			input_box.send_keys(Keys.ENTER)
# 		except:
# 			ss_name_sixth =  'whatsapp error ' + frappe.session.user + 'sixth' + frappe.generate_hash(length=5) +  '.png'
# 			f_sixth = save_file(ss_name_sixth, '', '','')
# 			driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_sixth.file_name)
# 			error_log_sixth = frappe.log_error(frappe.get_traceback(),"Error while trying to send the media file.")
# 			f_sixth.db_set('attached_to_doctype','Error Log')
# 			f_sixth.db_set('attached_to_name',error_log_sixth.name)
# 			frappe.db.commit()
# 			driver.quit()
# 			return False

# 	if attach_list:
# 		try:
# 			for path in attach_list:
# 				path_url = frappe.utils.get_bench_path() + "/sites" + path[1:]
# 				try:
# 					WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'span[data-icon="clip"]')))
# 				except:
# 					ss_name_seven =  'whatsapp error ' + frappe.session.user + 'seven' + frappe.generate_hash(length=5) +'.png'
# 					f_seven = save_file(ss_name_seven, '', '','')
# 					driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_seven.file_name)
# 					error_log_seven = frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message")
# 					f_seven.db_set('attached_to_doctype','Error Log')
# 					f_seven.db_set('attached_to_name',error_log_seven.name)
# 					frappe.db.commit()
# 					driver.quit()
# 					return False
# 				try:
# 					WebDriverWait(driver,60).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'span[data-icon="clip"]')))
# 				except:
# 					frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message")
# 					driver.quit()
# 					return False					
# 				driver.find_element_by_css_selector('span[data-icon="clip"]').click()
# 				attach=driver.find_element_by_css_selector('input[type="file"]')
# 				attach.send_keys(path_url)
# 				try:
# 					WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="app"]/div/div/div[2]/div[2]/span/div/span/div/div/div[2]/span/div/div')))
# 				except:
# 					ss_name_eight =  'whatsapp error ' + frappe.session.user + 'eight' + frappe.generate_hash(length=5) +  '.png'
# 					f_eight = save_file(ss_name_eight, '', '','')
# 					driver.save_screenshot(frappe.get_site_path('public','files') + '/'+ f_eight.file_name)
# 					error_log_eight = frappe.log_error(frappe.get_traceback(),"Unable to send the whatsapp message")
# 					f_eight.db_set('attached_to_doctype','Error Log')
# 					f_eight.db_set('attached_to_name',error_log_eight.name)
# 					frappe.db.commit()
# 					driver.quit()
# 					return False

# 				whatsapp_send_button = driver.find_element_by_xpath('//*[@id="app"]/div/div/div[2]/div[2]/span/div/span/div/div/div[2]/span/div/div')
# 				whatsapp_send_button.click()
	
# 		except:
# 			frappe.log_error(frappe.get_traceback(),"Error while trying to send the whatsapp message.")
# 			return False
# 	time.sleep(20)
# 	driver.quit()

# def remove_file_from_os(path):
# 	if os.path.exists(path):
# 		os.remove(path)
	
# def remove_qr_code(qr_hash):
# 	qr_path = frappe.get_site_path('public','files') + "/{}.png".format(frappe.session.user + qr_hash)
# 	remove_file_from_os(qr_path)

# # def remove_user_profile():
# # 	profiledir = os.path.join("./profiles/", "{}".format(frappe.session.user))
# # 	if os.path.exists(profiledir):
# # 		shutil.rmtree(profiledir)