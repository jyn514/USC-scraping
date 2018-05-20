EXAMS := $(addprefix exams/,$(addsuffix .html,Fall-2016 Fall-2017 Fall-2018 Summer-2016 Summer-2017 Summer-2018 Spring-2016 Spring-2017 Spring-2018))
DATA = .courses.data .sections.data

.PHONY: sql
sql: classes.sql

.PHONY: web server website
web server website: sql
	./app.py

.PHONY: dump
dump: sql
	./dump.py

# lxml has trouble with too much whitespace
define clean =
	if grep '404 page not found' $1; then \
		echo file "'$1'" gave a 404 not found; \
		rm $1; \
		exit 999; \
	fi
	sed -i 's/\s\+$$//' $1
endef

.SECONDEXPANSION:
.PHONY: courses sections
courses sections: webpages/USC_all_$$@.html

webpages:
	mkdir webpages

webpages/USC_all_%.html: | post.py webpages
	./$(firstword $|) $(subst .html,,$(subst webpages/USC_all_,,$@)) > $@
	$(call clean,$@)

exams:
	mkdir exams

exams/%.html: | post.py exams
	./$| `echo $@ | cut -d. -f1 | cut -d/ -f2 | cut -d- -f1` \
	     `echo $@ | cut -d. -f1 | cut -d- -f2` > $@
	$(call clean $@)

.courses.data: parse.py webpages/USC_all_courses.html
	./$< --catalog < $(lastword $^) > $@

.sections.data: parse.py webpages/USC_all_sections.html # | .exams.data
	./$< --sections < $(lastword $^) > $@

.exams.data: $(EXAMS) | parse.py
	./$| --exams

classes.sql: create_sql.py $(DATA)
	$(RM) $@
	# python2 compat
	PYTHONIOENCODING=utf-8 ./$<

.PHONY: clean
clean:
	$(RM) -r __pycache__
	$(RM) $(DATA) classes.sql *.pyc

.PHONY: clobber
clobber: clean
	$(RM) -r webpages

.PHONY: dist-clean
dist-clean: clobber
	git clean -dfx
